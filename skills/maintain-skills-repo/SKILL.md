---
name: maintain-skills-repo
description: Use when working on the wonderbell-skills repository, maintaining skill catalogs, reviewing local skill drift, or deciding whether to enable skills monitoring on a device.
---

# Maintain Skills Repo

## Overview

This skill is the entrypoint for maintaining the `wonderbell-skills` repository and its automation rules.

Use it to coordinate three kinds of work:

- catalog and source maintenance
- local skill drift review
- dialogue-driven monitoring setup on a device

## When to Use

- Updating `catalog/` files
- Reviewing newly detected local skills
- Deciding whether a local skill belongs in `custom`, `third_party`, or neither
- Setting up or revising monitoring on a machine
- Maintaining the long-term workflow of the `wonderbell-skills` repo

## Workflow

Follow the repository playbooks instead of improvising:

- For device setup and automation decisions, read [docs/automation-setup.md](../../docs/automation-setup.md)
- For day-to-day maintenance and review decisions, read [docs/skill-maintenance-playbook.md](../../docs/skill-maintenance-playbook.md)

Use the repo scripts when they fit:

- `scripts/install.sh`
- `scripts/audit-local-skills.py`
- `scripts/check-skill-drift.py`

## Rules

- Do not silently create recurring automation on a new device.
- Ask short confirmation questions when monitoring or durable repo updates have side effects.
- Prefer updating catalogs and docs only for durable changes.
- Keep routine machine state outside git.

## Common Mistakes

- Treating temporary local experiments as durable repository knowledge
- Updating the repo before confirming the user wants the change preserved
- Creating automation without confirming whether the device should be monitored
