#!/usr/bin/env python3
"""Deploy this repo to an Ubuntu server over SSH.

This is the Ubuntu-target parallel to `azure_deploy_container.py`.

It does NOT require Azure CLI or Key Vault. It copies the minimal set of files
needed for Docker Compose on the remote host and then runs:

  docker compose -f <base> -f <ubuntu-override> pull
  docker compose -f <base> -f <ubuntu-override> up -d --remove-orphans

Optionally syncs `.env` and `.env.secrets` to the remote host.

Security note: this script shells out to `ssh` and `rsync`.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], *, check: bool = True) -> None:
    subprocess.run(cmd, check=check)


def build_rsync_cmd(*, sources: list[Path], host: str, remote_dir: Path) -> list[str]:
    srcs = [str(p) for p in sources]
    # Trailing slash on remote_dir ensures rsync copies into the dir.
    dest = f"{host}:{str(remote_dir)}/"
    return ["rsync", "-az", "--mkpath", *srcs, dest]


def build_ssh_cmd(*, host: str, remote_command: str) -> list[str]:
    return ["ssh", host, remote_command]


def compose_remote_cmd(*, remote_dir: Path, compose_files: list[str], action: str) -> str:
    flags = " ".join([f"-f {shlex.quote(cf)}" for cf in compose_files])
    return f"cd {shlex.quote(str(remote_dir))} && docker compose {flags} {action}"


def main(argv: list[str] | None = None, repo_root_override: Path | None = None) -> None:
    parser = argparse.ArgumentParser(description="Deploy to Ubuntu server via SSH + Docker Compose")
    parser.add_argument("--host", required=True, help="SSH target in the form user@host")
    parser.add_argument(
        "--remote-dir",
        default="/opt/protected-container",
        help="Remote directory to sync files into (default: /opt/protected-container)",
    )
    parser.add_argument(
        "--compose-files",
        default=None,
        help=(
            "Comma-separated compose files relative to repo root (default: docker/docker-compose.yml,docker/docker-compose.ubuntu.yml)"
        ),
    )
    parser.add_argument(
        "--sync-secrets",
        action="store_true",
        help="Sync .env and .env.secrets to the remote dir before running docker compose",
    )

    args = parser.parse_args(argv)

    repo_root = repo_root_override or Path(__file__).resolve().parents[2]
    remote_dir = Path(str(args.remote_dir))

    compose_files = (
        [s.strip() for s in str(args.compose_files).split(",") if s.strip()]
        if args.compose_files
        else ["docker/docker-compose.yml", "docker/docker-compose.ubuntu.yml"]
    )

    # Validate required local files exist.
    required_paths: list[Path] = [repo_root / cf for cf in compose_files] + [repo_root / "docker"]
    missing = [str(p) for p in required_paths if not p.exists()]
    if missing:
        raise SystemExit(f"Missing required files: {missing}")

    print(f"[ubuntu-deploy] Target: {args.host}")
    print(f"[ubuntu-deploy] Remote dir: {remote_dir}")
    print(f"[ubuntu-deploy] Compose files: {compose_files}")

    # Ensure remote dir exists.
    _run(build_ssh_cmd(host=args.host, remote_command=f"mkdir -p {shlex.quote(str(remote_dir))}"))

    # Sync compose files and docker/ directory.
    sync_paths: list[Path] = [repo_root / cf for cf in compose_files] + [repo_root / "docker"]
    _run(build_rsync_cmd(sources=sync_paths, host=args.host, remote_dir=remote_dir))

    if bool(args.sync_secrets):
        env_paths: list[Path] = []
        for name in [".env", ".env.secrets"]:
            p = repo_root / name
            if p.exists():
                env_paths.append(p)
            else:
                print(f"[ubuntu-deploy] Skipping missing {p}")
        if env_paths:
            _run(build_rsync_cmd(sources=env_paths, host=args.host, remote_dir=remote_dir))
        else:
            print("[ubuntu-deploy] No env files to sync")

    # Pull and up on remote.
    pull_cmd = compose_remote_cmd(remote_dir=remote_dir, compose_files=compose_files, action="pull")
    up_cmd = compose_remote_cmd(remote_dir=remote_dir, compose_files=compose_files, action="up -d --remove-orphans")

    print("[ubuntu-deploy] Running remote pull...")
    _run(build_ssh_cmd(host=args.host, remote_command=pull_cmd))

    print("[ubuntu-deploy] Running remote up...")
    _run(build_ssh_cmd(host=args.host, remote_command=up_cmd))

    print("[ubuntu-deploy] Done.")


if __name__ == "__main__":
    main()
