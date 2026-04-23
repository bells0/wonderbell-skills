# Existing Skills Audit

This document records which existing local skills already cover important behavior, so new custom skills do not duplicate them.

## Why This Audit Exists

Before creating new custom skills, I reviewed the skills already installed under `~/.codex/skills`.

The goal was simple:

- reuse what already works
- avoid renaming existing behavior into duplicate skills
- create new skills only where there is a real gap

## Skills Already Covering Important Ground

### `brainstorming`

Already covers:

- exploring project context before implementation
- asking clarifying questions
- presenting approaches before execution
- getting user approval before moving into implementation

Conclusion:

Do **not** create a separate generic "ask-before-doing" skill.

### `verification-before-completion`

Already covers:

- requiring fresh evidence before claiming completion
- verifying instead of guessing
- refusing success claims without command output

Conclusion:

Do **not** create a second generic verification skill unless it addresses a much narrower domain-specific verification protocol.

### `writing-skills`

Already covers:

- how to structure a skill
- how to write useful descriptions
- how to validate whether a skill actually teaches the right behavior

Conclusion:

Use it as authoring guidance, not as something to replace.

### `skill-creator`

Already covers:

- what belongs in a skill
- what belongs in references or scripts
- how to structure a discoverable skill

Conclusion:

Reuse it when authoring or revising skills.

## Gaps Worth Filling

After reviewing current skills, two gaps stood out.

### 1. Context grounding as a first-class judgment

Missing behavior:

- when real source-of-truth artifacts exist, prefer them over model memory
- when fidelity matters, missing repo/screenshots/design system should block confident generation
- distinguish between "enough context to proceed" and "too little context, ask first"

This is now captured by `skills/ground-in-project-context`.

### 2. Exploration through variants instead of single-answer generation

Missing behavior:

- recognize when a task is exploratory rather than single-solution
- provide multiple directions instead of prematurely collapsing to one answer
- prefer one primary artifact with switchable variants over many disconnected forks

This is now captured by `skills/explore-with-variants`.

## Repository Rule

For this repository, the default rule is:

- if an existing installed skill already solves the problem, reuse it
- if the need is project-specific, document it in project docs
- only create a new skill when it encodes reusable judgment that is currently missing
