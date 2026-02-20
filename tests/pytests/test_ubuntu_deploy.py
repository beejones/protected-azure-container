from pathlib import Path

from scripts.deploy.ubuntu_deploy import build_rsync_cmd, build_ssh_cmd, compose_remote_cmd


def test_build_rsync_cmd_basic():
    cmd = build_rsync_cmd(
        sources=[Path("/repo/docker/docker-compose.yml"), Path("/repo/docker")],
        host="user@host",
        remote_dir=Path("/opt/protected-container"),
    )
    assert cmd[0] == "rsync"
    assert "user@host:/opt/protected-container/" in cmd


def test_build_ssh_cmd_basic():
    cmd = build_ssh_cmd(host="user@host", remote_command="echo hi")
    assert cmd == ["ssh", "user@host", "echo hi"]


def test_compose_remote_cmd_quotes_and_paths():
    remote = Path("/opt/protected-container")
    compose_files = ["docker/docker-compose.yml", "docker/docker-compose.ubuntu.yml"]
    out = compose_remote_cmd(remote_dir=remote, compose_files=compose_files, action="config")
    assert "cd /opt/protected-container" in out
    assert "docker compose" in out
    assert "-f docker/docker-compose.yml" in out
    assert "-f docker/docker-compose.ubuntu.yml" in out
    assert out.endswith(" config")
