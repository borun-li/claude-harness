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
