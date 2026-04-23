# Skill Maintenance Playbook

This document defines how an agent should reason about skill maintenance in day-to-day work.

It is designed for ongoing operation, not just first-time setup.

## Main Rule

Skill maintenance should be **event-driven and low-noise**.

That means:

- check routinely
- notify only on change
- ask before creating or changing recurring behavior
- update repository state only when the user wants durable changes

## What Counts As A Meaningful Change

The monitor should treat these as meaningful:

- a new local skill appears
- an existing local skill disappears
- a skill changes classification between `builtin`, `third_party`, `custom`, or `unknown`
- an `unknown` skill appears

These are the situations worth surfacing to the user.

## What The Agent Should Do When Change Is Detected

When the drift check reports a change, the agent should:

1. summarize the change
2. explain why it matters, if not obvious
3. recommend the next action
4. ask whether to update the repository catalogs or docs

The agent should not immediately rewrite tracked repository files unless the user confirms.

## Response Pattern For Detected Changes

When reporting changes, keep the message short and structured around action:

- what was added, removed, or reclassified
- whether any `unknown` skills were detected
- whether this looks like a catalog update, a third-party source update, or a local experiment

Then ask a focused question such as:

"Do you want me to update the catalogs for this change?"

## When To Update The Repository

The repository should be updated when:

- a new custom skill is meant to be kept
- a new third-party source should be tracked centrally
- a builtin or third-party classification was wrong and needs correction
- the maintenance rules themselves have changed

The repository should usually **not** be updated when:

- the change was temporary
- the user is experimenting locally
- the skill should remain device-local

## Review Expectations

Skill review should happen at two levels:

### 1. Structural review

Ask:

- is this skill already covered by an existing one?
- is the source classification correct?
- should it live in `custom`, `third_party`, or remain local only?

### 2. Content review

Ask:

- is the trigger condition clear?
- is the skill narrow enough?
- is it encoding reusable judgment rather than a one-off story?

## Agent Behavior Expectations

The agent should:

- prefer short confirmation questions over long questionnaires
- avoid creating recurring monitoring silently
- avoid writing routine audit snapshots into the repository
- prefer repository updates only for durable, reusable changes

## Default Maintenance Stance

For this repository, the default stance is:

- monitoring may run daily
- reminders should only happen when something changes
- routine state stays outside git
- durable knowledge belongs in the catalogs, scripts, or docs
