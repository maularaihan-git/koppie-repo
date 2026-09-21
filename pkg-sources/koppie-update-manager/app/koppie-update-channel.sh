#!/usr/bin/env bash
# Koppie Linux update channel switcher: stable (7-day ALA snapshot) or current
set -euo pipefail
MODE="${1:-}"
MIRRORLIST="/etc/pacman.d/mirrorlist"
BACKUP="/etc/pacman.d/mirrorlist.koppie-backup"

case "$MODE" in
  stable)
    SNAP=$(date -d "7 days ago" +"%Y/%m/%d")
    [ -f "$BACKUP" ] || cp "$MIRRORLIST" "$BACKUP"
    printf '## Koppie Linux - Stable channel (ALA snapshot %s)\nServer = https://archive.archlinux.org/repos/%s/$repo/os/$arch\n' "$SNAP" "$SNAP" > "$MIRRORLIST"
    echo "Switched to Stable channel (snapshot $SNAP)."
    ;;
  current)
    if [ -f "$BACKUP" ]; then
      cp "$BACKUP" "$MIRRORLIST"
      echo "Switched to Current channel (mirrors restored)."
    else
      echo "No backup found, mirrorlist left as-is." >&2
      exit 1
    fi
    ;;
  status)
    grep -m1 "^Server" "$MIRRORLIST" || true
    ;;
  *)
    echo "Usage: $0 {stable|current|status}" >&2
    exit 1
    ;;
esac
