---
name: design-taste
description: The user's personal interface design taste — usability over looks, fewest steps, keyboard-first, in-place feedback, thin-border hierarchy, restrained type and icons, and a list of generic AI-design defaults to avoid. Use when designing or reviewing any interface (flows, screens, components, Figma frames), or when the user asks for UI in their style. A project's own brand or context overrides it where they conflict.
---

# Design taste

**Precedence:** Constitution > the project's `project-context.md` and brand > this taste > defaults.
Accessibility rules are never traded for taste.

## 0. First principle

**Usability over looks.** Any decoration, animation or layout choice that slows, hides or
confuses the user's task is removed, however good it looks.

## 1. Product type decides four things

These four are confirmed by the user and recorded in the project's `project-context.md`; later
rounds reuse them. Never guess them:

1. Product class: tool, or visual / showcase / few pages.
2. Brand: colours and typefaces, or "none yet" (then fe-ui proposes them for approval).
3. Motion: restrained or rich, and any signature transition.
4. Copy tone: direct, warm, or formal.

State the class in the spec. The class then decides the rest:

| | Tool (used to get work done) | Visual / showcase, or few pages |
|---|---|---|
| Navigation | Left sidebar, collapsible | Top bar |
| Small screens (≤ 768 px) | Sidebar becomes an icon rail or a drawer; frequent actions stay one tap away | Top bar becomes a menu button |
| Keyboard | A shortcut for every frequent action, plus a command palette (⌘K / Ctrl+K) | Tab, Enter and Esc work; no command palette required |
| Dark mode | Required: every token has a light and a dark value | One mode, chosen by the brand; the other only when the user asks |
| Motion | Restrained: 150–200 ms fades and expands that explain a change | Richer transitions allowed |
| Boldness | None | Spent in one place: one signature moment (the first screen or a transition) |
| Copy | Short and direct; formal where rules must be followed | Warm where engagement matters (e.g. children) |
| Density | Body text 14 px; table rows 36–40 px | Moderate |

Every product honours the OS "reduce motion" setting.

## 2. Fewest steps

- The common task needs the fewest clicks and decisions; defaults decide for the user.
- **Editing depends on size:** one field → edit in place, auto-save; many fields → side drawer
  or a dedicated page. Never a modal for a single value.
- **Keyboard is first-class** (as §1 sets for the class): logical Tab order, Enter submits, Esc
  closes; shortcuts are shown in tooltips and menus.
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
- **Empty states** say what will appear here and offer the first action. Never a blank area or a
  bare "No data".

## 4. Visual language

- **Colour follows the project's brand palette**; status is never colour alone (text or icon too).
- **Type follows the brand.** With no brand yet, fe-ui proposes typefaces, a type scale and their
  roles for approval, and uses the system font stack until then. At most two families.
- **Hierarchy comes from 1 px thin borders** plus spacing and weight; no heavy shadows or
  gradients.
- **Spacing and shape:** a 4 px spacing scale; corner radius 4–6 px, matching the thin borders.
- **Icons:** the component library's own set; if it has none, Lucide. One set per project, never
  mixed; line style, to match the thin borders.
- **Dark mode** as §1 sets for the class; every mode meets contrast.
- No decoration that does not serve the task: no ornamental gradients, illustrations or icon
  clutter.

## 5. Components

Use the project's component library if it has one; otherwise pick a mature one (e.g. shadcn/ui,
Radix, Ant Design) for its accessibility and keyboard support. Never hand-build a component a
mature library already provides. In Figma, start from the chosen library's Figma kit; it also
saves Figma calls.

## 6. Never

- A dialog opened from inside a dialog.
- Decoration that serves no task.
- A frequent function buried more than two levels deep.
- A vague error.
- Anything beautiful that gets in the user's way.
- **Generic AI-design defaults:**
  - purple or blue gradients, or gradient backgrounds as decoration;
  - rows of identical rounded cards;
  - a hero of a big number, a small label and a gradient accent;
  - small all-caps labels above headings;
  - trailing arrows on links;
  - numbering or dividers that carry no information;
  - Inter, Roboto or Arial by default when the brand names none.

## 7. Review checklist

Each is yes/no; a "no" is a finding against the named user's task.

1. Product class stated?
2. Navigation matches the class (§1), including on small screens?
3. Motion and copy tone match the class?
4. The common task's step count is minimal; defaults used?
5. Single-field edits in place; multi-field edits in a drawer or page; no single-value modal?
6. Keyboard support as §1 sets for the class?
7. Feedback in place?
8. Errors give the cause and the next step?
9. Risky actions confirmed, naming what will be lost?
10. First load uses skeletons; user actions are optimistic and roll back in place?
11. Empty states say what will appear and offer the first action?
12. Thin-border hierarchy; brand colours; status not colour alone?
13. Type, spacing, radius and icons as §4; dark mode as §1?
14. None of §6?

Examples of each rule done well and badly: [examples.md](examples.md).

## 8. Where these preferences come from

Each preference here came from the user (interview, 2026-09-24; additions 2026-11-02). Only the user
changes this file. A new preference observed at acceptance or in post-launch feedback is proposed
by fe-ui as a candidate, with its source; it is added only after the user confirms.
