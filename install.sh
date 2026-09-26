#!/bin/sh
# Install this harness into ~/.claude (or $CLAUDE_HOME).
# Existing copies of the same folders are backed up first; nothing else in ~/.claude is touched.
# Usage: ./install.sh            install or update
#        ./install.sh --check    only check prerequisites
set -eu

here=$(cd "$(dirname "$0")" && pwd)
dest=${CLAUDE_HOME:-$HOME/.claude}
parts="CONSTITUTION.md agents commands backend frontend route gates hooks skills/design-taste"

missing=0
need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1 ($2)"; missing=1; }; }
need python3 "gates and the git hook"
need node "frontend evidence capture"
need npm "installs playwright-core for the gates"
need git "the harness assumes a git project"
command -v go >/dev/null 2>&1 || echo "note: go not found (only needed for Go projects such as ithaca-local-guide)"
[ -d "/Applications/Google Chrome.app" ] || command -v google-chrome >/dev/null 2>&1 \
  || echo "note: Google Chrome not found; frontend capture drives the system Chrome"
[ "$missing" = 0 ] || { echo "install the missing tools and rerun"; exit 1; }
[ "${1:-}" = "--check" ] && { echo "prerequisites ok"; exit 0; }

mkdir -p "$dest"

# Back up whatever this install would overwrite.
existing=""
for p in $parts; do [ -e "$dest/$p" ] && existing="$existing $p"; done
if [ -n "$existing" ]; then
  backup="$dest/backup-harness-$(date +%Y%m%d-%H%M%S).tgz"
  (cd "$dest" && tar czf "$backup" --exclude node_modules $existing)
  echo "backed up:$existing -> $backup"
fi

for p in $parts; do
  mkdir -p "$dest/$(dirname "$p")"
  rm -rf "$dest/$p.tmp-install"
  cp -R "$here/$p" "$dest/$p.tmp-install"
  if [ -d "$dest/$p/node_modules" ]; then mv "$dest/$p/node_modules" "$dest/$p.tmp-install/"; fi
  rm -rf "$dest/$p"
  mv "$dest/$p.tmp-install" "$dest/$p"
done
echo "installed into $dest"

# Register the no-tree-restoring-git hook in settings.json (idempotent; other settings untouched).
python3 - "$dest/settings.json" <<'EOF'
import json, os, sys
path = sys.argv[1]
cmd = 'python3 "$HOME/.claude/hooks/no-tree-restoring-git.py"'
s = json.load(open(path)) if os.path.exists(path) else {}
pre = s.setdefault("hooks", {}).setdefault("PreToolUse", [])
if any(h.get("command") == cmd for e in pre for h in e.get("hooks", [])):
    print("hook already registered")
else:
    pre.append({"matcher": "Bash", "hooks": [{"type": "command", "command": cmd}]})
    json.dump(s, open(path, "w"), indent=2)
    print("hook registered in settings.json")
EOF

(cd "$dest/gates" && npm ci --silent) && echo "gates dependencies installed"
echo "done. Restart Claude Code, then run /route in a project."
