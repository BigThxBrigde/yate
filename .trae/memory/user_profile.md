# User Profile

## Preferences / Conventions

- **Plan documents location (2026-09-15):** All implementation plans must be
  generated under `.trae/documents/` at the project root, using a short
  descriptive filename (e.g. `{NAME}_plan.md`). This folder is git-ignored.
- **Relative paths only (2026-09-15):** Plans and documents must use
  repository-root-relative paths (e.g. `yate/app.py`). Never use absolute
  paths or `file://` links.
- **English for `.trae` documents (2026-09-15):** Every document generated
  under `.trae/` (including plans and memory files) must be written in
  English.
- **Project-local preference storage (2026-09-15):** AI/assistant
  preference changes must be recorded in the project-local `.trae/` folder
  (this file / project memory), not in the global user memory directory.
