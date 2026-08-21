# GitHub Publishing Commands

## Before publishing

1. Apache-2.0 is included in `LICENSE`; confirm the owner accepts it.
2. Replace `[DEMO_URL]` and `[GITHUB_URL]` in LinkedIn files.
3. Confirm no secrets/PII/databases are tracked.
4. Run deterministic tests and inspect `git status`.

## Create a new repository

Create an empty GitHub repository named, for example, `satellite-x`, without auto-generating README/license/gitignore.

Then run locally:

```bash
cd satellite-x
git init
git branch -M main
git add .
git status
# Inspect the complete staged file list before committing.
git commit -m "Release SATELLITE-X v0.8.0 verified demo"
git remote add origin https://github.com/YOUR_USERNAME/satellite-x.git
git push -u origin main
```

Prefer GitHub CLI authentication rather than embedding tokens in a URL:

```bash
gh auth login
gh repo create satellite-x --public --source=. --remote=origin --push
```

## Create release

```bash
git tag -a v0.8.0 -m "SATELLITE-X v0.8.0"
git push origin v0.8.0
gh release create v0.8.0 \
  /path/to/SATELLITE-X_v0.8.0_DEMO_GITHUB_READY.zip \
  --title "SATELLITE-X v0.8.0" \
  --notes-file GITHUB_RELEASE_NOTES_v0.8.0.md
```

## Never do this

```text
Do not paste a GitHub token into source code, notebook, README, issue, chat or remote URL.
Do not commit .env, private keys, farmer data, raw photos, production DBs or official traffic traces.
```
