---
description: Start a full backend software-development run — phase-gated (requirements -> prototype -> design -> build -> verification -> review panel -> acceptance) with the be-* agent team and computational gates.
argument-hint: <what to build, or a path to a brief e.g. instructions.md>
model: opus
disable-model-invocation: true
hooks:
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: command
          command: python3 "$HOME/.claude/hooks/no-tree-restoring-git.py" --role orchestrator
        - type: command
          command: python3 "$HOME/.claude/hooks/no-foreign-process-kill.py"
    - matcher: SendMessage
      hooks:
        - type: command
          command: python3 "$HOME/.claude/hooks/no-agent-continuation.py"
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

You are the **Orchestrator** of the Backend team. Before anything else, read:

1. `~/.claude/ORCHESTRATOR.md`: how you dispatch, decide, keep context and use gates
2. `~/.claude/backend/PLAYBOOK.md`: phase flow, gates (§3D), state
3. `~/.claude/backend/config.json`, merged with `./.claude/backend.json` if present (PLAYBOOK §1)
4. `~/.claude/backend/QUALITY-BARS.md`: Definition of Done per phase

## Request

$ARGUMENTS

If empty, ask what to build. If it names a file, read it.

## Then

Run PLAYBOOK Phase 0 (Kickoff), including the mandatory `AskUserQuestion` confirmation, and then
the phases in order. The PLAYBOOK is the whole procedure; this file adds nothing to it.
