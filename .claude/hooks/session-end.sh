#!/usr/bin/env bash
#
# SessionEnd hook: on each session end, spawn a headless Claude to commit and
# push everything changed during the session.
#
# Wired from .claude/settings.json under hooks.SessionEnd.
#
# NOTE: a SessionEnd hook runs a shell command, not a Claude prompt. To "run a
# prompt" we launch a fresh headless `claude -p`. That headless session ITSELF
# ends and would fire SessionEnd again -> infinite loop. The sentinel env var
# below breaks that recursion: the headless child inherits it and exits early.

set -euo pipefail

# --- recursion guard -------------------------------------------------------
# The headless claude we spawn inherits this var; its own SessionEnd hook sees
# it set and exits immediately.
if [[ -n "${CLAUDE_AUTO_COMMIT_RUNNING:-}" ]]; then
  exit 0
fi
export CLAUDE_AUTO_COMMIT_RUNNING=1

# --- locate project + binary ----------------------------------------------
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/home/clickhouse/invoicepilot}"
CLAUDE_BIN="/home/clickhouse/.local/bin/claude"
LOG_FILE="$PROJECT_DIR/.claude/hooks/session-end.log"
PID_FILE="$PROJECT_DIR/.claude/hooks/session-end.pid"

cd "$PROJECT_DIR"

# Nothing changed? Don't bother spawning Claude.
if [[ -z "$(git status --porcelain)" ]]; then
  echo "$(date -Iseconds) SessionEnd: working tree clean, nothing to commit" >> "$LOG_FILE"
  exit 0
fi

echo "$(date -Iseconds) SessionEnd: changes detected, launching headless commit+push" >> "$LOG_FILE"

# --- run the prompt headlessly, fully detached -----------------------------
# A SessionEnd hook is reaped when the parent CLI exits (and carries a timeout),
# so a synchronous slow commit+push gets killed mid-flight. We detach the
# headless run into its own session (setsid) so it outlives the parent, and
# background it (&) so the hook returns immediately. Its PID is recorded so the
# run can be checked on later.
#
# --permission-mode bypassPermissions lets the headless run execute git without
# interactive approval (it has no TTY). Bash is the only tool it needs.
PROMPT="Commit and push all files that were changed during this session. Stage all modified, added, and deleted tracked files (respect .gitignore), write a concise conventional-commit message summarizing the changes, commit, and push to the current branch's upstream. If there is nothing to commit, do nothing."

setsid bash -c '
  cd "$1" || exit 1
  echo "$(date -Iseconds) SessionEnd: detached runner started (pid $$)" >> "$2"
  before=$(git rev-parse HEAD 2>/dev/null || echo "")
  if "$3" --permission-mode bypassPermissions -p "$4" >> "$2" 2>&1; then
    after=$(git rev-parse HEAD 2>/dev/null || echo "")
    if [[ -n "$before" && "$before" != "$after" ]]; then
      count=$(git rev-list --count "$before..$after" 2>/dev/null || echo "?")
      echo "$(date -Iseconds) SessionEnd: commit+push finished ($count new commit(s)):" >> "$2"
      git log --no-color --format="  %h %s" "$before..$after" >> "$2" 2>&1
      echo "$(date -Iseconds) SessionEnd: files committed:" >> "$2"
      git diff --no-color --stat "$before" "$after" | sed "s/^/  /" >> "$2" 2>&1
    else
      echo "$(date -Iseconds) SessionEnd: headless run finished but HEAD unchanged (nothing committed)" >> "$2"
    fi
  else
    echo "$(date -Iseconds) SessionEnd: headless run failed (see above)" >> "$2"
  fi
  rm -f "$5"
' _ "$PROJECT_DIR" "$LOG_FILE" "$CLAUDE_BIN" "$PROMPT" "$PID_FILE" >/dev/null 2>&1 &

# Record the detached session leader's PID and stop waiting on it.
echo "$!" > "$PID_FILE"
disown 2>/dev/null || true
echo "$(date -Iseconds) SessionEnd: detached headless runner (pid $(cat "$PID_FILE"))" >> "$LOG_FILE"
