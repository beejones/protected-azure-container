#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-ronny@192.168.1.45}"
PUBKEY_PATH="${2:-$HOME/.ssh/id_rsa.pub}"

if [[ ! -f "$PUBKEY_PATH" ]]; then
  echo "Public key not found: $PUBKEY_PATH" >&2
  echo "Usage: $0 [user@host] [path/to/public_key.pub]" >&2
  exit 1
fi

echo "Installing key from: $PUBKEY_PATH"
echo "Target host: $HOST"

cat "$PUBKEY_PATH" | ssh "$HOST" '
  set -e
  umask 077
  mkdir -p "$HOME/.ssh"
  touch "$HOME/.ssh/authorized_keys"
  key="$(cat)"
  grep -qxF "$key" "$HOME/.ssh/authorized_keys" || echo "$key" >> "$HOME/.ssh/authorized_keys"
  chmod 700 "$HOME/.ssh"
  chmod 600 "$HOME/.ssh/authorized_keys"
'

echo "Key installed. Testing key-based auth..."
ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" "echo KEY_AUTH_OK"
echo "Done."
