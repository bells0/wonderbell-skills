# Contributing

Changes to `wonderbell-skills` follow a branch → pull request → review → merge workflow so that decisions, implementation steps, verification, and approvals remain traceable.

## Development workflow

1. Start from the latest default branch and create a focused feature branch. Do not develop directly on `main`.
2. Keep one independently reviewable purpose per branch and pull request.
3. Make atomic commits with messages that explain the completed outcome.
4. Run the checks relevant to the changed catalogs, installer, documentation, or first-party Skill.
5. Push the feature branch and open a pull request using the repository template.
6. Ask an independent reviewer or the repository owner to review it. An author does not approve their own work.
7. Merge only after required checks pass, review comments are resolved, and the repository owner authorizes the merge.

Direct changes or pushes to the default branch are reserved for an explicitly authorized emergency. The pull request or follow-up record must explain the exception.

## Pull request expectations

Every pull request should record:

- why the change is needed;
- what changed and what stayed out of scope;
- verification commands and results;
- source, attribution, and license changes;
- risks, dependencies, and rollback notes;
- the reviewer or owner approval.

Avoid rewriting a branch after review has begun because it can invalidate earlier comments and evidence. If a rewrite is unavoidable, call it out and request a fresh review.

## Repository checks

Run the repository checks that apply to the change:

```bash
bash scripts/test-install.sh
bash scripts/test-audit-local-skills.sh
bash scripts/test-check-skill-drift.sh
git diff --check
```

For a changed first-party Skill, also run its own tests and validation instructions. Do not replace a real-path check with a mock when the real path is part of the requested acceptance.

## Public-source hygiene

- Never commit credentials, private source material, or machine-specific audit snapshots.
- Keep generated state outside Git.
- Preserve upstream repositories, attribution, and nested licenses for external or separately licensed Skills.
- Do not enable an external catalog entry until its repository and declared Skill path are reachable.
