# Requirements — Duplicate upload message

- Author: be-analyst (frontend-only run) · Status: draft

## 0. Understanding
- **Asked:** "when someone uploads a file we already have, tell them and let them open the original"
- **Means:** the upload page shows the backend's existing 409 duplicate answer instead of a generic error
- **Ambiguities:** none blocking

## 1. Requirements
### REQ-001 — Tell the user the file already exists [interface]
- **Cut:** above
- **Behaviour:** A refused duplicate upload says so and links to the original.
- **Accept:** Given file 17 stored, When it is uploaded again, Then the user reads it exists and can open 17
- **Source:** "tell them and let them open the original"
- **Fixtures:** n/a — frontend run

## 2. Non-goals
- Changing the duplicate rule itself (backend, shipped).

## 3. Open questions
| # | Question | Default | Blocks |
|---|---|---|---|
