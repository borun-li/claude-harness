# Design taste — examples

Each pair shows a rule in `SKILL.md` done badly, then well.

## Error message (§3: errors name the cause and the next step)

- **Bad:** "Something went wrong."
- **Good:** "Upload failed: the file is over 20 MB. Compress it or choose a smaller file." Shown
  under the upload field, not in a toast.

## Editing a single value (§2: edit in place, auto-save)

- **Bad:** clicking "Rename" opens a modal with one text field, "Save" and "Cancel".
- **Good:** the name turns into a text field where it stands; Enter or leaving the field saves it,
  Esc cancels; if saving fails, the old name returns and the reason appears under the field.

## Risky action (§3: confirm, naming what will be lost)

- **Bad:** "Are you sure?" with "OK" and "Cancel".
- **Good:** "Delete 'Q3 report' and its 12 comments? This cannot be undone." with "Delete report"
  and "Keep it".

## Empty state (§3: say what will appear, offer the first action)

- **Bad:** a blank table area, or "No data".
- **Good:** "Your uploaded files will appear here." with an "Upload your first file" button in the
  empty area.

## In-place feedback (§3: no toast for what the screen already shows)

- **Bad:** after "Save", a toast in the top-right corner says "Saved successfully".
- **Good:** the button briefly reads "Saved ✓" where it was clicked; a failure shows its reason
  under the button.

## Optimistic update and rollback (§3: optimistic, rolled back in place)

- **Bad:** clicking "Like" shows a spinner until the server answers.
- **Good:** the like shows at once; if the server rejects it, the like is undone and "Couldn't
  like: you're offline. Try again." appears next to the button.

## Status not colour alone (§4)

- **Bad:** a red dot beside a job.
- **Good:** a red dot with the word "Failed" (or an error icon), so it reads without colour.

## Generic AI-design first screen (§6)

- **Bad:** a gradient background, a big number with a small all-caps label above it, and three
  identical rounded cards with trailing-arrow links.
- **Good (tool class):** the first screen is the user's task list itself, with the frequent action
  at hand; hierarchy from thin borders and type weight, no decoration.
