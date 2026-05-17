# GitHub Pages setup

Steps for you to perform once, after pushing the new `docs/`,
`mkdocs.yml`, and `.github/workflows/docs.yml` to GitHub.

**Estimated time: ~2 minutes.** Everything else is already wired up.

## Why this is safe for your existing `shrenikm.github.io`

GitHub gives every account *two kinds* of Pages sites:

1. **User site** at `https://shrenikm.github.io` — backed by a repo
   literally named `shrenikm/shrenikm.github.io`. This is what you
   already have.
2. **Project sites** at `https://shrenikm.github.io/<repo-name>/` —
   one per regular repo, backed by that repo. This is what we want for
   nimbus.

The two are **completely independent**. Enabling a project site on
`shrenikm/nimbus` does not touch the `shrenikm.github.io` repo, does not
modify your user-site content, and does not change any DNS / CNAME
settings on `shrenikm.com`. Nimbus's docs will live at:

```
https://shrenikm.github.io/nimbus/
```

That's it. No subdomain, no custom domain, no overlap with anything you
already host.

## What I've already done in this repo

- `docs/` — five-page documentation site (index, getting-started,
  bucket-types, cli, api, testing).
- `mkdocs.yml` — Material theme + mkdocstrings for auto-generated API
  reference. `site_url` is pinned to
  `https://shrenikm.github.io/nimbus/`.
- `pyproject.toml` — new `[docs]` optional-deps group with `mkdocs`,
  `mkdocs-material`, `mkdocstrings`, `mkdocstrings-python`.
- `.github/workflows/docs.yml` — builds on every push to `main` that
  touches `docs/`, `src/nimbus/**`, `mkdocs.yml`, or `pyproject.toml`,
  then deploys via GitHub's official `actions/deploy-pages@v4`.
- `.gitignore` — `site/` (the local build output) is ignored.
- `README.md` — trimmed to a hook + link to the docs.
- `AGENTS.md` — adds a "Docs are part of the contract" section so
  future changes keep docs in sync.

## What you need to do

### 1. Push the new files

```
git add docs mkdocs.yml pyproject.toml .github README.md AGENTS.md .gitignore SETUP_GITHUB_PAGES.md
git commit -m "docs: add MkDocs Material site + GitHub Pages workflow"
git push origin main
```

The workflow will run automatically. It'll fail at the "deploy" step the
first time, because Pages isn't enabled yet. That's expected. Move to
step 2.

### 2. Enable Pages with the *GitHub Actions* source

1. Go to <https://github.com/shrenikm/nimbus/settings/pages>.
2. Under **Build and deployment**, set:
   - **Source:** `GitHub Actions` (NOT "Deploy from a branch").
3. Save. There's nothing else to configure on this screen.

!!! warning "Important: choose 'GitHub Actions', not 'Deploy from a branch'"
    The workflow uses the modern artifact-based deploy
    (`actions/deploy-pages`), not the older `gh-pages`-branch model. If
    you pick "Deploy from a branch", nothing will publish.

### 3. Re-run the workflow

1. Go to <https://github.com/shrenikm/nimbus/actions>.
2. Click on the latest "Deploy docs to GitHub Pages" run.
3. Hit **Re-run all jobs** in the top-right.

(Alternatively: push any small change to `main`, or use the **Run
workflow** button on the workflow page to trigger it manually.)

### 4. Verify

Within ~2 minutes of a successful workflow run, the site goes live at:

```
https://shrenikm.github.io/nimbus/
```

The first deploy can take an extra minute or two for DNS to propagate.
After that, every push to `main` that touches docs / source / config
will rebuild and redeploy automatically.

## What this does NOT touch

- `https://shrenikm.github.io` (your user site) — completely untouched.
- `shrenikm.com` — completely untouched. No CNAME files are committed.
- Any other repo on your account.
- Any DNS records on your domain.

## If something goes wrong

| Symptom | Likely cause |
|---|---|
| Workflow's `build` step fails | Probably broken mkdocstrings reference or bad markdown. Run `mkdocs build --strict` locally to reproduce. |
| Workflow's `deploy` step fails with permissions error | Pages source isn't set to "GitHub Actions". See step 2. |
| Site URL returns 404 after deploy | First deploy can take a few minutes. Refresh after 5 minutes. |
| Site shows wrong URL in links | Check `site_url` in `mkdocs.yml` matches `https://shrenikm.github.io/nimbus/`. |

## Local preview

To preview docs locally before pushing:

```
conda activate nimbus
uv pip install -e ".[docs]"
mkdocs serve
```

Then open <http://127.0.0.1:8000> in your browser. Edits hot-reload.

## Future maintenance

You shouldn't need to do anything else, ever. The workflow handles
rebuilds and redeploys. The only ongoing maintenance is **updating
`docs/` whenever the code changes** — there's a section in `AGENTS.md`
covering this.
