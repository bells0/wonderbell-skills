---
name: ground-in-project-context
description: Use when output quality depends on an existing codebase, design system, screenshots, assets, or other project artifacts and the agent must avoid guessing from memory.
---

# Ground In Project Context

## Overview

When real project artifacts exist, they are the source of truth. Read them before generating from memory.

## When to Use

- Recreating or extending an existing UI
- Working from a repo, PRD, screenshots, Figma, or design system
- High-fidelity work where exact values matter
- Any task that risks becoming generic if context is skipped

## Rules

- Identify the source of truth first: files, assets, screenshots, docs, or schemas.
- Prefer observed values and behavior over remembered patterns.
- If key context is missing and quality would suffer, ask for it early.
- Treat "I roughly know what this looks like" as a warning sign, not a shortcut.

## Process

1. Name the artifacts that define the task.
2. Read the smallest useful set of those artifacts first.
3. Extract exact constraints: structure, tokens, copy, behavior, or data shape.
4. Only then propose, generate, or implement.

## Common Mistakes

- Starting from intuition while the repo is available
- Using generic patterns when project-specific ones exist
- Asking vague questions instead of requesting the missing source material directly
