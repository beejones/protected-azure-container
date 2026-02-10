# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Breaking Changes

- **Environment Variable Separation**: Configuration is now split into 4 files to improve security and clarity.
    - `.env`: Runtime non-secret configuration (e.g. `BASIC_AUTH_USER`).
    - `.env.secrets`: Runtime secrets (e.g. `BASIC_AUTH_HASH`, `APP_SECRET`). **Uploaded to Key Vault as `env-secrets`.**
    - `.env.deploy`: Deploy-time non-secret configuration (e.g. `AZURE_LOCATION`).
    - `.env.deploy.secrets`: Deploy-time secrets (e.g. `GHCR_TOKEN`). **Used locally, not uploaded.**

- **Migration Steps**:
    1. Move `BASIC_AUTH_HASH` from `.env` to `.env.secrets`.
    2. Move `GHCR_TOKEN` from `.env.deploy` to `.env.deploy.secrets`.
    3. Ensure your deploy scripts/pipelines populate `.env.secrets` and `.env.deploy.secrets` appropriately.

### Added

- Support for `.env.secrets` and `.env.deploy.secrets`.
- `azure_deploy_container.py` arguments: `--upload-secrets-file`, `--upload-secrets-secret-name`.
- `azure_start.sh` now fetches both `env` and `env-secrets` from Key Vault.
- `gh_sync_actions_env.py` supports syncing `.env.secrets` to GitHub Secrets.
