# Agent Operating Principles

These notes capture the operating principles I most want to preserve when designing or refining agents.

## 1. Treat agents as workflow systems

A useful agent is not just a model with a tone. It needs:

- a role
- a sequence of work
- clear completion criteria
- failure and verification behavior

## 2. Use real context before model memory

If the truth already exists in code, assets, screenshots, docs, or schemas, read that first.

Model memory can help interpret context. It should not replace context.

## 3. Ask before ambiguous work

Questions are not politeness. They are uncertainty reduction.

When the request is ambiguous and quality depends on intent, constraints, or existing systems, clarify before generating.

## 4. Prefer protocols over vague capabilities

A capability becomes reliable when the agent knows:

- what triggers it
- what state it reads
- what state it writes
- how the host and the agent coordinate

## 5. Verification belongs inside the system

Users should not be the first thing that catches breakage.

A good agent workflow verifies outputs before handoff whenever practical.

## 6. Exploration tasks need variants

Not every task is "find the answer." Many are "search the space."

In those tasks, agents should expose multiple directions and make tradeoffs easier to compare.

## 7. Keep skills narrow and composable

Avoid giant skills that try to own everything.

Prefer skills that encode one reusable judgment pattern clearly enough that they can be combined with other existing skills.
