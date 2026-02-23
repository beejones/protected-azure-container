"""Register an app's domain with the centralized Caddy proxy on Ubuntu.

Ensures the proxy Caddyfile contains a reverse-proxy site block for the
deployed app.  Idempotent — skips if the block exists; appends and restarts
Caddy when missing.

Called by :func:`ubuntu_deploy.main` as a post-deploy step when
``PUBLIC_DOMAIN`` is set and external Caddy integration is detected.
"""
from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Container name (from docker/proxy/docker-compose.yml).
DEFAULT_CADDY_CONTAINER = "central-proxy"

# Template for the site block.  Placeholders: {domain}, {service}, {port}.
SITE_BLOCK_TEMPLATE = """\

# -------------------------
# {domain} Route (auto-registered)
# -------------------------
{domain} {{
    tls {{$ACME_EMAIL}}
    encode gzip
    header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
    reverse_proxy {service}:{port}
}}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ssh_run(
    host: str,
    cmd: str,
    *,
    check: bool = True,
    capture: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess:
    """Run *cmd* on *host* via SSH."""
    full = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        host,
        cmd,
    ]
    return subprocess.run(
        full,
        input=input_text,
        capture_output=capture,
        text=True,
        check=check,
    )


def _domain_present(caddyfile_text: str, domain: str) -> bool:
    """Return True if *domain* already has a site block."""
    pattern = re.compile(r"^\s*" + re.escape(domain) + r"\s*\{", re.MULTILINE)
    return bool(pattern.search(caddyfile_text))


def _resolve_caddyfile_path(remote_dir: Path | str) -> str:
    """Derive the remote Caddyfile path from the upstream convention.

    The proxy stack lives at ``<remote_dir>/docker/proxy/Caddyfile``.
    On the server the bind-mount source is one level up from the current app
    (the protected-container repo), so we fall back to the parent path when
    the app-local path does not exist.
    """
    return str(Path(remote_dir) / "docker" / "proxy" / "Caddyfile")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ensure_caddy_registration(
    *,
    ssh_host: str,
    domain: str,
    service: str,
    port: str | int,
    caddyfile_path: str,
    caddy_container: str = DEFAULT_CADDY_CONTAINER,
    dry_run: bool = False,
) -> bool:
    """Ensure *domain* has a site block in the remote Caddyfile.

    Returns True if the block was added, False if already present.
    Raises on SSH or validation failure.
    """
    port = str(port)

    # 1. Read current Caddyfile from the host  ───────────────────────────
    result = _ssh_run(ssh_host, f"cat {shlex.quote(caddyfile_path)}", check=False)
    if result.returncode != 0:
        # Caddyfile not found — proxy stack not deployed yet.  Skip silently.
        print(
            f"[caddy-register] ⚠️  Caddyfile not found at {caddyfile_path} — "
            f"proxy stack may not be deployed yet.  Skipping Caddy registration."
        )
        return False

    caddyfile_text = result.stdout

    # 2. Already registered?  ────────────────────────────────────────────
    if _domain_present(caddyfile_text, domain):
        print(f"[caddy-register] ✔  {domain} already registered")
        return False

    # 3. Build the site block  ───────────────────────────────────────────
    block = SITE_BLOCK_TEMPLATE.format(domain=domain, service=service, port=port)

    if dry_run:
        print(f"[caddy-register] [dry-run] Would append to {caddyfile_path}:")
        print(block)
        return True

    # 4. Append to host Caddyfile  ──────────────────────────────────────
    append_cmd = f"tee -a {shlex.quote(caddyfile_path)} > /dev/null"
    full = [
        "ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
        ssh_host, append_cmd,
    ]
    proc = subprocess.run(full, input=block, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Failed to append Caddy block on {ssh_host}: {proc.stderr.strip()}"
        )

    # 5. Verify the write  ──────────────────────────────────────────────
    result2 = _ssh_run(ssh_host, f"cat {shlex.quote(caddyfile_path)}")
    if not _domain_present(result2.stdout, domain):
        raise RuntimeError(
            f"Appended Caddy block for {domain} but it was not found on re-read"
        )

    # 6. Restart Caddy to pick up bind-mount changes & obtain cert  ─────
    print(f"[caddy-register] ⏳ Restarting {caddy_container} to pick up config …")
    _ssh_run(ssh_host, f"docker restart {shlex.quote(caddy_container)}")

    # Brief wait for Caddy to boot, then validate config inside container.
    validate_cmd = (
        f"sleep 3 && docker exec {shlex.quote(caddy_container)} "
        f"caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile"
    )
    _ssh_run(ssh_host, validate_cmd)

    print(f"[caddy-register] ✅ Registered {domain} → {service}:{port}")
    return True
