# GHCR_TOKEN (GitHub Container Registry)

`GHCR_TOKEN` is a GitHub Personal Access Token used to authenticate to **GitHub Container Registry** (`ghcr.io`).

You need it when:
- your image is **private** and Azure Container Instances (ACI) must **pull** it, or
- you run scripts that **build + push** images to `ghcr.io` from your machine.

## Create a token

Recommended (simplest): **classic** PAT.

In GitHub: **Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token**.

Minimum scopes:
- `read:packages` (pull private images)
- `write:packages` (push images)

If the package is associated with a **private** repository, you may also need:
- `repo`

Notes:
- If your org enforces SSO, you must authorize the token for SSO.
- Treat this token like a password.

## Where to put it

Local deploy (ACI via `scripts/azure_deploy_container.py`): set these in `.env.deploy`:

- `GHCR_PRIVATE=true`
- `GHCR_USERNAME=<your-github-username-or-org>`
- `GHCR_TOKEN=<your-pat>`

GitHub Actions deploy:
- store `GHCR_TOKEN` as a repository **Secret**
- store `GHCR_USERNAME` as a repository **Variable**

If you use `python3 scripts/gh_sync_actions_env.py --set`, it will sync these from `.env.deploy`.

Note: `python3 scripts/azure_deploy_container.py` (run locally) syncs GitHub Actions vars/secrets by default; use `--no-set-vars-secrets` to disable (CI does this).

## Quick verification

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin
docker pull ghcr.io/<owner>/protected-azure-container:latest
```

If you accidentally paste a token into chat/logs, revoke it immediately and generate a new one.
