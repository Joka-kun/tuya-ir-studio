#!/usr/bin/env bash
# Copies only IR Studio. Does not touch keys, LocalTuya, Tuya Cloud or network.
set -euo pipefail
CONFIG="${1:-/config}"
SOURCE="$(cd "$(dirname "$0")" && pwd)/custom_components/ir_studio"
DEST="$CONFIG/custom_components/ir_studio"
if [ ! -d "$CONFIG" ]; then
  echo "HA config directory not found: $CONFIG" >&2
  echo "Usage: ./install_ir_studio.sh /path/to/ha-config" >&2
  exit 1
fi
if [ ! -f "$SOURCE/manifest.json" ]; then
  echo "Missing IR Studio source next to install script" >&2; exit 1
fi
mkdir -p "$CONFIG/custom_components"
if [ -d "$DEST" ]; then
  BACKUP="$CONFIG/custom_components/ir_studio.backup.$(date +%Y%m%d-%H%M%S)"
  cp -a "$DEST" "$BACKUP"
  echo "Backed up existing IR Studio to $BACKUP"
fi
mkdir -p "$DEST"
cp -a "$SOURCE/." "$DEST/"
echo "Tuya IR Studio files installed in $DEST"
echo "Now restart Home Assistant and add integration: Settings > Devices & Services > Add Integration > Tuya IR Studio"
echo "This installer did NOT change YRC11 local key, device registry, LAN or other integrations."
