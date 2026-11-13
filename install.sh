#!/bin/sh
# Install this harness into ~/.claude (or $CLAUDE_HOME).
# Existing copies are backed up first. In agents/ and commands/ only the harness's own files are
# written or removed; your files there and everything else in ~/.claude are left alone.
# Usage: ./install.sh            install or update
#        ./install.sh --check    only check prerequisites
set -eu

here=$(cd "$(dirname "$0")" && pwd)
dest=${CLAUDE_HOME:-$HOME/.claude}
# Owned: replaced whole. Shared: you may keep your own agents and commands there, so only the
# harness's files are written, and only files an earlier harness put there are removed.
owned="CONSTITUTION.md ORCHESTRATOR.md backend frontend route gates hooks skills/design-taste"
shared="agents commands"
parts="$owned $shared"
manifest="$dest/.harness-files"
retired="agents/fe-critic.md agents/fe-designer.md"   # shipped before the manifest existed

missing=0
need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1 ($2)"; missing=1; }; }
need python3 "gates and the safety hooks"
need node "frontend evidence capture"
need npm "installs playwright-core for the gates"
need git "the harness assumes a git project"
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

for p in $owned; do
  mkdir -p "$dest/$(dirname "$p")"
  rm -rf "$dest/$p.tmp-install"
  cp -R "$here/$p" "$dest/$p.tmp-install"
  if [ -d "$dest/$p/node_modules" ]; then mv "$dest/$p/node_modules" "$dest/$p.tmp-install/"; fi
  rm -rf "$dest/$p"
  mv "$dest/$p.tmp-install" "$dest/$p"
done

previous=$( { [ -f "$manifest" ] && cat "$manifest"; echo $retired | tr ' ' '\n'; } | sort -u)
for f in $previous; do
  [ -e "$here/$f" ] || { [ -f "$dest/$f" ] && rm -f "$dest/$f" && echo "removed retired $f"; } || true
done
for d in $shared; do
  mkdir -p "$dest/$d"
  cp "$here/$d"/*.md "$dest/$d/"
done
(cd "$here" && for d in $shared; do ls "$d"/*.md; done) > "$manifest"
echo "installed into $dest"

# The safety hooks are declared in the harness's agent and command files, so they run only in
# harness sessions. Remove the global entries earlier versions added (other settings untouched).
python3 - "$dest/settings.json" <<'EOF'
import json, os, sys
path = sys.argv[1]
if not os.path.exists(path):
    sys.exit(0)
old = {'python3 "$HOME/.claude/hooks/no-tree-restoring-git.py"',
       'python3 "$HOME/.claude/hooks/no-foreign-process-kill.py"',
       'python3 "$HOME/.claude/hooks/no-agent-continuation.py"'}
s = json.load(open(path))
pre = s.get("hooks", {}).get("PreToolUse")
if not pre:
    sys.exit(0)
kept, removed = [], 0
for e in pre:
    hs = [h for h in e.get("hooks", []) if h.get("command") not in old]
    removed += len(e.get("hooks", [])) - len(hs)
    if hs or not e.get("hooks"):
        kept.append({**e, "hooks": hs})
if removed:
    if kept:
        s["hooks"]["PreToolUse"] = kept
    else:
        del s["hooks"]["PreToolUse"]
        if not s["hooks"]:
            del s["hooks"]
    json.dump(s, open(path, "w"), indent=2)
    print(f"removed {removed} global harness hook entries from settings.json; they now run only in harness sessions")
EOF

(cd "$dest/gates" && npm ci --silent) && echo "gates dependencies installed"
echo "done. Restart Claude Code, then run /route in a project."
