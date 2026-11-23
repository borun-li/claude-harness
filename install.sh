#!/bin/sh
# Install this harness into ~/.claude (or $CLAUDE_HOME, for a test install).
#
# Replaced whole:   CONSTITUTION.md ORCHESTRATOR.md backend/ frontend/ route/ gates/ harness/
#                   (harness/ holds the default config.json and the CHANGELOG)
# Shared with you:  agents/ commands/ hooks/ — only the harness's own files are written, and only
#                   files an earlier install recorded (.harness-files) are removed, plus the
#                   harness's retired /backend* and /frontend* commands; yours stay.
# Yours to edit:    skills/design-taste/ — replaced only while it is still the copy an install
#                   put there; an edited copy is kept.
# Never touched:    harness-local/ (your own defaults: harness-local/config.json) and everything
#                   else in ~/.claude.
# What an install could overwrite is backed up first (backup-harness-<date>.tgz).
#
# Usage: ./install.sh              install or update
#        ./install.sh --check      only check prerequisites
#        ./install.sh --uninstall  remove what install wrote; prints what it leaves
set -eu

here=$(cd "$(dirname "$0")" && pwd)
dest=${CLAUDE_HOME:-$HOME/.claude}
owned="CONSTITUTION.md ORCHESTRATOR.md backend frontend route gates harness"
shared="agents commands hooks"
# The commands of the two-team layout, retired in 16.0.0.
old_commands="backend frontend backend-resume frontend-resume backend-status frontend-status backend-config frontend-config"
skill="skills/design-taste"
manifest="$dest/.harness-files"
skill_record="$dest/.harness-design-taste"

case "$#:${1:-}" in
  0:) mode=install ;;
  1:--check) mode=check ;;
  1:--uninstall) mode=uninstall ;;
  *) echo "usage: ./install.sh [--check | --uninstall]   (at most one flag, given alone)" >&2; exit 2 ;;
esac

# The harness's files in the shared directories, as paths relative to the repo and to $dest.
shipped() { (cd "$here" && ls agents/*.md commands/*.md hooks/*.py); }
# What an earlier install recorded there. Anything that is not a plain file name in a shared
# directory is ignored, so a damaged manifest cannot point a removal elsewhere.
recorded() {
  if [ -f "$manifest" ]; then grep -E '^(agents|commands|hooks)/[^/]+$' "$manifest" | sort -u || true; fi
}
# Remove the retired commands an install left without recording them (installs older than the
# manifest): a harness command names the Constitution, a command of the user's own is kept.
remove_old_commands() {
  for n in $old_commands; do
    f="commands/$n.md"
    if [ ! -e "$here/$f" ] && [ -f "$dest/$f" ] && grep -q '~/\.claude/CONSTITUTION\.md' "$dest/$f"; then
      rm -f "$dest/$f"; echo "removed retired $f"
    fi
  done
}
# A checksum of a directory's file names and content: tells an edited copy from an installed one.
tree_sum() {
  (cd "$1" && find . -type f ! -name .DS_Store | LC_ALL=C sort | while IFS= read -r f; do cksum "$f"; done | cksum)
}

if [ "$mode" = uninstall ]; then
  [ -d "$dest" ] || { echo "nothing to uninstall: $dest does not exist"; exit 0; }
  recorded | while IFS= read -r f; do
    if [ -f "$dest/$f" ]; then rm -f "$dest/$f"; fi
  done
  remove_old_commands >/dev/null
  for p in $owned; do rm -rf "$dest/$p"; done
  kept_skill=""
  if [ -d "$dest/$skill" ]; then
    now=$(tree_sum "$dest/$skill")
    if { [ -f "$skill_record" ] && [ "$now" = "$(cat "$skill_record")" ]; } || [ "$now" = "$(tree_sum "$here/$skill")" ]; then
      rm -rf "$dest/$skill"
    else
      kept_skill=1
    fi
  fi
  rm -f "$manifest" "$skill_record"
  for d in $shared skills; do rmdir "$dest/$d" 2>/dev/null || true; done
  echo "removed the harness from $dest"
  echo "left in place:"
  backups=$(ls "$dest"/backup-harness-*.tgz 2>/dev/null | wc -l | tr -d ' ')
  if [ "$backups" != 0 ]; then echo "  $dest/backup-harness-*.tgz ($backups, each a backup of what an install replaced)"; fi
  if [ -d "$dest/harness-local" ]; then echo "  $dest/harness-local/ (your own defaults)"; fi
  if [ -n "$kept_skill" ]; then echo "  $dest/$skill/ (you edited it)"; fi
  reports=${TMPDIR:-/tmp}
  reports=${reports%/}/harness-reports
  if [ -d "$reports" ]; then echo "  $reports/ (agent reports kept between handback and return)"; fi
  counters=$(find "$dest/projects" -name 'agent-*.continuations' 2>/dev/null | wc -l | tr -d ' ')
  if [ "$counters" != 0 ]; then echo "  $counters continuation counters next to session transcripts ($dest/projects/**/agent-*.continuations)"; fi
  echo "  your own agents, commands and hooks, settings.json and everything else in $dest"
  exit 0
fi

missing=0
need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1 ($2)"; missing=1; }; }
need python3 "gates and the safety hooks; 3.9 or newer"
need node "frontend evidence capture; 18 or newer"
need npm "installs playwright-core for the gates"
need git "the harness assumes a git project"
if command -v python3 >/dev/null 2>&1 && ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
  echo "too old: $(python3 --version 2>&1) (the gates and the safety hooks need Python 3.9 or newer)"
  missing=1
fi
if command -v node >/dev/null 2>&1; then
  node_major=$(node --version 2>/dev/null | sed 's/^v//; s/\..*//')
  case "$node_major" in '' | *[!0-9]*) node_major=0 ;; esac
  if [ "$node_major" -lt 18 ]; then
    echo "too old: node $(node --version 2>&1) (frontend evidence capture needs Node.js 18 or newer)"
    missing=1
  fi
fi
has_chrome() {
  if [ -n "${CHROME_PATH:-}" ] && [ -e "$CHROME_PATH" ]; then return 0; fi
  if [ -d "/Applications/Google Chrome.app" ]; then return 0; fi
  for c in google-chrome google-chrome-stable chromium chromium-browser; do
    if command -v "$c" >/dev/null 2>&1; then return 0; fi
  done
  return 1
}
has_chrome || echo "note: no Chrome or Chromium found (CHROME_PATH, the macOS app, or google-chrome / google-chrome-stable / chromium / chromium-browser on PATH); frontend capture drives the system browser"
[ "$missing" = 0 ] || { echo "install or update the tools above and rerun"; exit 1; }
[ "$mode" = check ] && { echo "prerequisites ok"; exit 0; }

mkdir -p "$dest"

# Back up whatever this install could overwrite.
existing=""
for p in $owned $skill $shared; do [ -e "$dest/$p" ] && existing="$existing $p"; done
if [ -n "$existing" ]; then
  backup="$dest/backup-harness-$(date +%Y%m%d-%H%M%S).tgz"
  (cd "$dest" && tar czf "$backup" --exclude node_modules $existing)
  echo "backed up:$existing -> $backup"
fi

for p in $owned; do
  rm -rf "$dest/$p.tmp-install"
  cp -R "$here/$p" "$dest/$p.tmp-install"
  if [ -d "$dest/$p/node_modules" ]; then mv "$dest/$p/node_modules" "$dest/$p.tmp-install/"; fi
  rm -rf "$dest/$p"
  mv "$dest/$p.tmp-install" "$dest/$p"
done
cp "$here/CHANGELOG.md" "$dest/harness/CHANGELOG.md"

# skills/design-taste: an edited copy (one that is neither the new default nor what an install
# recorded) is the user's and is kept.
new_sum=$(tree_sum "$here/$skill")
if [ -d "$dest/$skill" ]; then cur_sum=$(tree_sum "$dest/$skill"); else cur_sum=""; fi
if [ -f "$skill_record" ]; then old_sum=$(cat "$skill_record"); else old_sum=""; fi
if [ -n "$cur_sum" ] && [ "$cur_sum" != "$new_sum" ] && [ "$cur_sum" != "$old_sum" ]; then
  echo "kept your edited $dest/$skill; the new default is $here/$skill (delete yours and rerun to take it)"
else
  mkdir -p "$dest/skills"
  rm -rf "$dest/$skill.tmp-install"
  cp -R "$here/$skill" "$dest/$skill.tmp-install"
  rm -rf "$dest/$skill"
  mv "$dest/$skill.tmp-install" "$dest/$skill"
  echo "$new_sum" > "$skill_record"
fi

# Shared directories: remove what an earlier install recorded and this one no longer ships, then
# write the harness's files. Every other file there is the user's.
recorded | while IFS= read -r f; do
  if [ ! -e "$here/$f" ] && [ -f "$dest/$f" ]; then rm -f "$dest/$f"; echo "removed retired $f"; fi
done
remove_old_commands
for d in $shared; do mkdir -p "$dest/$d"; done
shipped | while IFS= read -r f; do cp "$here/$f" "$dest/$f"; done
shipped > "$manifest"
version=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["harness_version"])' "$here/harness/config.json")
echo "installed harness $version into $dest"
old_local=""
for n in backend frontend; do
  if [ -f "$dest/harness-local/$n.json" ]; then old_local="$old_local harness-local/$n.json"; fi
done
if [ -n "$old_local" ]; then
  echo "note:$old_local no longer read: merge into harness-local/config.json (models are now under \"models\")"
fi

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

# --loglevel=error: one line when it works, the cause when it does not.
if (cd "$dest/gates" && npm ci --no-audit --no-fund --loglevel=error); then
  echo "gates dependencies installed"
else
  echo "error: npm ci failed in $dest/gates (see above). The files are installed, but frontend evidence capture cannot run until it succeeds: fix npm and rerun ./install.sh" >&2
  exit 1
fi
echo "done. Restart Claude Code, then run /route in a project."
