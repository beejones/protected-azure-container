#!/bin/bash
# Azure startup script for protected container
# Fetches secrets from Key Vault and starts the application

set -e

echo "[azure_start] Starting protected container..."

# If AZURE_KEYVAULT_URI is set, fetch the .env from Key Vault
if [ -n "$AZURE_KEYVAULT_URI" ]; then
    echo "[azure_start] Fetching secrets from Key Vault: $AZURE_KEYVAULT_URI"
    
    # Login using Managed Identity
    az login --identity --allow-no-subscriptions 2>/dev/null || {
        echo "[azure_start] Warning: Could not login with Managed Identity, trying without auth"
    }
    
    # Extract vault name from URI (https://<vault-name>.vault.azure.net/)
    VAULT_NAME=$(echo "$AZURE_KEYVAULT_URI" | sed -E 's|https://([^.]+)\.vault\.azure\.net/?|\1|')
    
    # Fetch the 'env' secret and write to .env
    if az keyvault secret show --vault-name "$VAULT_NAME" --name "env" --query "value" -o tsv > /home/coder/.env 2>/dev/null; then
        echo "[azure_start] Successfully fetched .env from Key Vault"
        chown coder:coder /home/coder/.env
        export $(grep -v '^#' /home/coder/.env | xargs -d '\n')
    else
        echo "[azure_start] Warning: Could not fetch 'env' secret from Key Vault"
    fi

    # Fetch the 'env-secrets' secret and write to .env.secrets
    if az keyvault secret show --vault-name "$VAULT_NAME" --name "env-secrets" --query "value" -o tsv > /home/coder/.env.secrets 2>/dev/null; then
        echo "[azure_start] Successfully fetched .env.secrets from Key Vault"
        chown coder:coder /home/coder/.env.secrets
        chmod 600 /home/coder/.env.secrets
        export $(grep -v '^#' /home/coder/.env.secrets | xargs -d '\n')
    else
        echo "[azure_start] Warning: Could not fetch 'env-secrets' secret from Key Vault"
    fi
else
    echo "[azure_start] No AZURE_KEYVAULT_URI set, using local environment"
    
    # If .env exists locally, source it
    if [ -f /home/coder/.env ]; then
        export $(grep -v '^#' /home/coder/.env | xargs -d '\n')
    fi
fi

# Ensure workspace directory exists
mkdir -p /home/coder/workspace
chown -R coder:coder /home/coder/workspace
mkdir -p /app/logs
chown -R coder:coder /app/logs

export LOG_DATE="$(date +%Y-%m-%d)"

echo "[azure_start] Starting application..."

# Execute the command passed to the container
exec "$@"
