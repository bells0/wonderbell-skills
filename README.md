# wonderbell-skills

Personal Codex skills, notes, and operating principles maintained in a public GitHub repository.

This repository is the source of truth for my custom skills. It is designed to be:

- easy to version and share
- safe to keep public
- separate from built-in/vendor-provided skills
- simple to sync into `~/.codex/skills`

## What This Repo Contains

- `skills/`: custom reusable skills I want to maintain long-term
- `docs/`: design notes, audits, and operating principles behind the skills
- `catalog/`: inventory of builtin and third-party skills managed through this repo
- `scripts/`: helper scripts for installing repo skills into my local Codex setup

## What This Repo Does Not Contain

This repo does **not** re-publish built-in or vendor-provided skills that already ship with Codex or other toolchains.

Instead, I keep:

- my own custom skills here
- an audit of built-in skills in [docs/existing-skills-audit.md](docs/existing-skills-audit.md)
- guidance on what should be reused versus what is worth creating from scratch

That keeps the repository legally cleaner and reduces duplication.

## Current Custom Skills

- `ground-in-project-context`
- `explore-with-variants`

## Install Locally

This repository is meant to live anywhere on disk, then act as the control plane for my skills setup.

The installer handles three layers:

- custom skills from this repo
- builtin skills recorded in `catalog/builtins.yaml`
- third-party skills declared in `catalog/third-party.yaml`

From the repo root:

```bash
bash scripts/install.sh
```

The installer:

- creates `~/.codex/skills` if needed
- symlinks each custom skill folder from this repo into `~/.codex/skills`
- verifies builtin skills listed in the catalog are present
- can fetch enabled third-party git-based skills into `vendor/`
- refuses to overwrite existing non-symlink paths

## Updating Skills

My intended workflow is:

1. edit skills in this repo
2. commit and push to GitHub
3. run `bash scripts/install.sh` again if new skills were added

Existing symlinks will continue pointing at the current checkout, so edits to files here are immediately reflected locally.

To enforce that all required builtin skills are present:

```bash
STRICT_BUILTINS=1 bash scripts/install.sh
```

## Repository Philosophy

This repo is shaped by one core idea:

**A good skill should encode a reusable judgment pattern, not just a one-off story.**

That means:

- project-specific rules belong in project docs, not general skills
- skills should be narrow, discoverable, and composable
- built-in skills should be reused when they already solve the problem
- new skills should only exist when they add real value

See [docs/existing-skills-audit.md](docs/existing-skills-audit.md) for the initial inventory and rationale.
