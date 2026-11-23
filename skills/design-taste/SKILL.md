---
name: design-taste
description: The user's personal interface design taste — usability over looks, fewest steps, keyboard-first, in-place feedback, thin-border hierarchy, restrained type and icons, and a list of generic AI-design defaults to avoid. Use when designing or reviewing any interface (flows, screens, components, Figma frames), or when the user asks for UI in their style. A project's own brand or context overrides it where they conflict.
---

# Design taste

**Precedence:** the project's brand and written context > this taste > a model's defaults.
Accessibility rules are never traded for taste.

Each rule carries its reason. Where a case is not written here, apply the reason, not the nearest
rule.

## 0. First principle

**Usability over looks.** Any decoration, animation or layout choice that slows, hides or
confuses the user's task is removed, however good it looks.

## 1. Product type decides four things

These four are confirmed by the user and recorded in the project's written context; later rounds
reuse them. Never guess them:

1. Product class: tool, or visual / showcase / few pages.
2. Brand: colours and typefaces, or "none yet" (then the designer proposes them for approval).
3. Motion: restrained or rich, and any signature transition.
4. Copy tone: direct, warm, or formal.

State the class in the spec. The class then decides the rest:

| | Tool (used to get work done) | Visual / showcase, or few pages |
|---|---|---|
| Navigation | Left sidebar, collapsible | Top bar |
| Small screens (≤ 768 px) | Sidebar becomes an icon rail or a drawer; frequent actions stay one tap away | Top bar becomes a menu button |
| Keyboard | A shortcut for every frequent action, plus a command palette (⌘K / Ctrl+K) | Tab, Enter and Esc work; no command palette required |
| Dark mode | Required: every token has a light and a dark value | One mode, chosen by the brand; the other only when the user asks |
| Motion | 150 ms for a fade or a colour change, 200 ms for something that moves or changes size; only to show what changed | Richer transitions allowed |
| Boldness | None | Spent in one place: one signature moment (the first screen or a transition) |
| Copy | Short and direct; formal where rules must be followed | Warm where engagement matters (e.g. children) |
| Density | Body text 14 px; table rows 36–40 px | Moderate |

Why the tool column reads as it does: a tool is used for hours and by habit. A sidebar keeps every
section one click away and leaves the content its width; shortcuts and density pay back on the
hundredth use; motion and boldness cost a little attention every time they are seen, so a tool
spends none on them.

Every product honours the OS "reduce motion" setting.

## 2. Fewest steps

Before any screen, write three lines; the rest of this section is applied to them:

1. **Who:** the named user, in the project's words.
2. **Their most frequent task:** the one thing they come here to do most often.
3. **Steps:** how many clicks and decisions that task takes today (none yet, for a new product)
   and how many it takes in this design.

A line you cannot fill is a question for the user or a fact to read from the product, never a
guess: a design for an unnamed user's unnamed task has nothing to make shorter.

- The common task needs the fewest clicks and decisions; defaults decide for the user. Every
  decision the product gets right is one the user does not make.
- **Editing depends on size:** one field → edit in place, auto-save; many fields → side drawer
  or a dedicated page. Never a modal for a single value: it hides the page the value belongs to
  and adds an open and a close to a one-step job.
- **Keyboard is first-class** (as §1 sets for the class): logical Tab order, Enter submits, Esc
  closes; shortcuts are shown in tooltips and menus, so they are learned while using the mouse.
- Secondary information and actions are **collapsed** ("More" menu, expandable section), not
  shown by default and not hover-only: shown by default they compete with the main task;
  hover-only they do not exist on touch or keyboard.
- Frequent functions are at most two levels deep: a third level is one the user has to remember.

## 3. Feedback and states

- **Feedback in place:** results appear where the action happened (next to the button, under
  the field), because that is where the user is looking. No toast for something the screen
  already shows: it pulls the eye away and then disappears.
- **Errors name the cause and the next step**, since a cause is the only thing the user can act
  on. "Something went wrong" is never enough.
- **Risky actions** (delete, overwrite) ask for confirmation, naming what will be lost. "Are you
  sure?" is answered by habit; a named loss is read.
- **Loading:** skeleton screens on first load, so the layout that is coming is already in place
  and nothing jumps; optimistic updates for user actions, rolled back with an in-place message on
  failure, because the action succeeds nearly every time and should feel instant. No full-page
  spinners: they hide what has already loaded.
- **Empty states** say what will appear here and offer the first action. A blank area or a bare
  "No data" reads as broken.

## 4. Visual language

- **Colour follows the project's brand palette**; status is never colour alone (text or icon
  too): colour alone is lost to colour-blind users and in a grey-scale screenshot.
- **Type follows the brand.** With no brand yet, the designer proposes typefaces, a type scale and
  their roles for approval, and uses the system font stack until then. At most two families: a
  third stops reading as hierarchy.
- **Hierarchy comes from 1 px thin borders** plus spacing and weight; no heavy shadows or
  gradients. A border says where one thing ends without adding a layer to look at; shadow and
  gradient add depth that means nothing in a flat task.
- **Spacing:** a 4 px scale: 4, 8, 12, 16, 24, 32. One scale keeps alignment from being decided
  again on every screen.
- **Shape:** corner radius 4 px on controls (buttons, inputs, tags), 6 px on containers (cards,
  drawers, dialogs): close to square, to match the thin borders.
- **Icons:** the component library's own set; if it has none, Lucide. One set per project, never
  mixed, so one meaning always looks the same; line style, to match the thin borders.
- **Dark mode** as §1 sets for the class; every mode meets contrast.
- No decoration that does not serve the task: no ornamental gradients, illustrations or icon
  clutter.

## 5. Components

Use the project's component library if it has one; otherwise pick a mature one (e.g. shadcn/ui,
Radix, Ant Design): its accessibility and keyboard support are already tested. Never hand-build a
component a mature library already provides. In a design tool, start from the chosen library's
own kit, so the design is made of what will be built.

## 6. Never

- A dialog opened from inside a dialog.
- Decoration that serves no task.
- A frequent function buried more than two levels deep.
- A vague error.
- Anything beautiful that gets in the user's way.

**A model's defaults, and what to do instead.** These are what a model reaches for when nothing
tells it otherwise. A project's brief or brand may ask for one of them; without that, do the right
column.

| The default | Instead |
|---|---|
| Purple or blue gradients, or a gradient background as decoration | A flat surface in the brand's neutral; colour only where it means something (status, the primary action) |
| Rows of identical rounded cards | A list or a table with thin dividers; a card only for an object the user opens or acts on as a whole |
| A hero of a big number, a small label and a gradient accent | The first screen is the user's most frequent task; a number appears with what it is compared to and the action it leads to |
| Small all-caps labels above headings | One heading in sentence case that says it by itself |
| Trailing arrows on links | Link text that says where it goes |
| Numbering or dividers that carry no information | Numbers only for a real sequence; a divider only where the content changes kind; otherwise spacing |
| Inter, Roboto or Arial by default when the brand names none | The system font stack until the brand's typefaces are approved (§4) |

## 7. Review checklist

Each is yes/no; a "no" is a finding against the named user's task. Where the interface can be
run, items 12–14 are read from the running page (the fonts, radii, backgrounds and open dialogs it
really has), not from the code.

1. Product class stated?
2. Navigation matches the class (§1), including on small screens?
3. Motion and copy tone match the class?
4. The three lines of §2 written; the common task's step count is minimal; defaults used?
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

Each preference here came from the user (interview, 2026-09-24; additions 2026-11-02; reasons,
values and replacements confirmed 2026-11-22). Only the user changes this file. A new preference
observed at acceptance or in post-launch feedback is proposed as a candidate, with its source; it
is added only after the user confirms.
