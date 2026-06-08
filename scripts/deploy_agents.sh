#!/usr/bin/env bash
# Deploy the source-controlled subagent templates to ~/.claude/agents/.
#
# By default it symlinks (so edits in the repo take effect immediately).
# Pass --copy to install copies instead. Pass --uninstall to remove them.
#
# Usage:
#   scripts/deploy_agents.sh            # symlink agents/*/*.md -> ~/.claude/agents/
#   scripts/deploy_agents.sh --copy     # copy instead of symlink
#   scripts/deploy_agents.sh --uninstall

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$REPO_ROOT/agents"
DEST_DIR="$HOME/.claude/agents"

MODE="symlink"
case "${1:-}" in
  --copy) MODE="copy" ;;
  --uninstall) MODE="uninstall" ;;
  "" ) ;;
  * ) echo "unknown option: $1" >&2; exit 2 ;;
esac

mkdir -p "$DEST_DIR"

shopt -s nullglob
agents=("$SRC_DIR"/*/*.md)
if [ ${#agents[@]} -eq 0 ]; then
  echo "No agent templates found in $SRC_DIR" >&2
  exit 1
fi

for src in "${agents[@]}"; do
  name="$(basename "$src")"
  dest="$DEST_DIR/$name"
  case "$MODE" in
    uninstall)
      if [ -L "$dest" ] || [ -f "$dest" ]; then rm -f "$dest"; echo "removed  $dest"; fi
      ;;
    copy)
      cp -f "$src" "$dest"; echo "copied   $name -> $dest"
      ;;
    symlink)
      ln -sfn "$src" "$dest"; echo "linked   $name -> $dest"
      ;;
  esac
done

echo "Done ($MODE). Agents in $DEST_DIR:"
ls -1 "$DEST_DIR" | sed 's/^/  /'
