---
name: design-taste
description: The user's personal interface design taste — usability over looks, fewest steps, keyboard-first, in-place feedback, thin-border hierarchy, dark mode. Use when designing or reviewing any interface (fe-designer specs, fe-critic design-system lens), or when the user asks for UI in their style. A project's own brand or context overrides it where they conflict.
---

# Design taste

**Precedence:** Constitution > the project's `project-context.md` and brand > this taste > defaults.
Accessibility rules are never traded for taste.

## 0. First principle

**Usability over looks.** Any decoration, animation or layout choice that slows, hides or
confuses the user's task is removed, however good it looks.

## 1. Product type decides four things

**Confirmed with the user before any design.** These depend on the product, so the orchestrator
asks at kickoff (frontend PLAYBOOK §2.4) and records the answers in the project's
`project-context.md`; later rounds reuse them. Never guess them:

1. Product class: tool, or visual / showcase / few pages.
2. Brand colours: the palette, or "none yet" (then propose one for approval).
3. Motion: restrained or rich, and any signature transition.
4. Copy tone: direct, warm, or formal.

State the class in the spec.

| | Tool (used to get work done) | Visual / showcase, or few pages |
|---|---|---|
| Navigation | Left sidebar, collapsible | Top bar |
| Motion | Restrained: 150–200 ms fades and expands that explain a change | Richer transitions allowed |
| Copy | Short and direct; formal where rules must be followed | Warm where engagement matters (e.g. children) |
| Density | Moderate | Moderate |

Every product honours the OS "reduce motion" setting.

## 2. Fewest steps

- The common task needs the fewest clicks and decisions; defaults decide for the user.
- **Editing depends on size:** one field → edit in place, auto-save; many fields → side drawer
  or a dedicated page. Never a modal for a single value.
- **Keyboard is first-class:** every frequent action has a shortcut; a command palette (⌘K /
  Ctrl+K); logical Tab order, Enter submits, Esc closes. Shortcuts are shown in tooltips/menus.
- Secondary information and actions are **collapsed** ("More" menu, expandable section), not
  shown by default and not hover-only.
- Frequent functions are at most two levels deep.

## 3. Feedback and states

- **Feedback in place:** results appear where the action happened (next to the button, under
  the field). No toast for something the screen already shows.
- **Errors name the cause and the next step.** "Something went wrong" is never enough.
- **Risky actions** (delete, overwrite) ask for confirmation, naming what will be lost.
- **Loading:** skeleton screens on first load; optimistic updates for user actions, rolled back
  with an in-place message on failure. No full-page spinners.

## 4. Visual language

- **Colour follows the project's brand palette**; status is never colour alone (text or icon too).
- **Hierarchy comes from 1 px thin borders** plus spacing and weight; no heavy shadows or
  gradients.
- **Dark mode is required**: every token has a light and a dark value, both meeting contrast.
- No decoration that does not serve the task: no ornamental gradients, illustrations or icon
  clutter.

## 5. Components

Use the project's component library if it has one; otherwise pick a mature one (e.g. shadcn/ui,
Radix, Ant Design) for its accessibility and keyboard support. Never hand-build a component a
mature library already provides.

## 6. Never

- A dialog opened from inside a dialog.
- Decoration that serves no task.
- A frequent function buried more than two levels deep.
- A vague error.
- Anything beautiful that gets in the user's way.

## 7. Review checklist (fe-critic, design-system lens)

Each is yes/no; a "no" is a finding against the named user's task.

1. Product class stated, and navigation, motion and copy match it?
2. The common task's step count is minimal; defaults used?
3. Single-field edits in place; multi-field edits in a drawer or page; no single-value modal?
4. Shortcut for each frequent action, plus a command palette?
5. Feedback in place; errors give cause and next step?
6. Risky actions confirmed; loading uses skeletons and optimistic updates?
7. Thin-border hierarchy; brand colours; status not colour alone; dark mode for every token?
8. No nested dialogs, decoration without purpose, or functions deeper than two levels?
