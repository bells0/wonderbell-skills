# Automation Setup

This document defines how an agent should help set up skills monitoring on a new device.

The goal is not silent automation. The goal is **guided setup through dialogue**.

## Principle

On a new device, the agent should not automatically create recurring monitoring.

Instead, the agent should:

1. detect that the repository and scripts are available
2. explain what monitoring does in plain language
3. ask whether monitoring should be enabled on this device
4. confirm configuration choices through short dialogue
5. only then create the automation

## Why Dialogue Is Required

Monitoring is not a purely mechanical setup step.

Different devices may have different roles:

- primary work machine
- temporary machine
- experimental machine
- low-noise machine where reminders should be minimized

Because of that, the agent should treat monitoring as an opt-in workflow, not a default side effect of installation.

## What The Agent Should Explain

Before asking for confirmation, the agent should explain:

- the monitor checks local skill state against the repository catalogs
- it compares against a stored baseline
- it only needs to notify when a change is detected
- it does not write daily reports into the repository

The explanation should be short. The user only needs enough context to decide.

## Required Questions

When setting up monitoring on a device, the agent should confirm:

1. whether monitoring should be enabled on this device
2. whether the device should use the default daily schedule
3. whether the monitor should only notify on changes

In this repository, the current recommended defaults are:

- enable monitoring: yes, only on real work machines
- schedule: daily
- notify behavior: only when changes are detected

## Recommended Dialogue Pattern

The agent should ask in a short sequence, not as a long form.

Suggested flow:

1. "This repo can monitor local skill drift and only notify when something changes. Do you want that enabled on this device?"
2. If yes: "Use the default schedule of once per day?"
3. If yes: "Keep it quiet unless a change is detected?"
4. After confirmation: create the automation and summarize what was configured

## When The Agent Should Skip Setup

The agent should skip creating monitoring when:

- the user explicitly declines
- this device is temporary or not a normal work machine
- the required scripts or catalogs are missing
- the environment does not support creating the automation

In those cases, the agent should explain the reason briefly and stop.

## What Should Be Recorded

The recurring automation should use:

- `scripts/check-skill-drift.py`
- the repository catalogs
- a state file outside the repo, such as `~/.codex/state/wonderbell-skills-drift.json`

The automation should not write routine reports into tracked files.

## After Setup

After the monitor is created, the agent should summarize:

- whether monitoring is enabled
- the schedule
- that reminders only happen when changes are detected

That summary should be short and should not dump implementation detail unless the user asks.
