# requirements/ (archive)

Original source material the project was built from. **`docs/` supersedes this folder** and is the source of truth for business and technical rules.

- `Business/`: Word drafts of the build guide and blueprint, written with different tools. Several overlap.
- `Technical/`: early blueprint, architecture and folder-structure notes; superseded by `docs/TECHNICAL/`.
- `Screens/`: screen references.

Canonical file (the one `docs/BUSINESS/01-BUSINESS-REQUIREMENTS.md` cites):
`Business/stock-and-options-trading-system-build-guide.docx`

`Business/archive/` holds superseded drafts (ChatGPT, Claude, Copilot and long-blueprint variants) moved there with `git mv`; they remain in git history.

`Screens/` is currently empty (git does not track empty folders).

## Claude Code

`Business/`, `Technical/` and `Screens/` are denied for Read/Grep in `.claude/settings.json` to save context. To consult a file, convert it on demand (for example `pandoc <file>.docx -t gfm`, which needs pandoc installed; it is not installed on this machine) or ask Claude to, or temporarily remove the matching deny entries and restore them afterwards.
