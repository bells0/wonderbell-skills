# Agent System Engineering Methodology Notes

These are provisional methodology notes derived from studying Claude Code source architecture patterns. They are not system skills, installed skills, or catalog entries.

Use this document as a candidate pool for future project trials. After these methods prove useful in real projects, selected parts may be converted into narrow skills with clear triggers, checklists, and verification behavior.

## Status

- Documentation only.
- Not creating skills yet.
- Pending validation through real project use.
- No files under `skills/` should be created from this note yet.
- No catalog or README skill-list updates should happen until a method graduates into an actual skill.

## Method Areas

### 1. Runtime and System Design

**When to use:** Designing an agent host, CLI, app extension, MCP server, or workflow runtime where model calls, tools, state, and user interaction need predictable coordination.

**Core practice:** Treat the agent as a runtime system, not a prompt. Name the execution boundaries, durable state, transient state, tool interfaces, cancellation paths, and recovery behavior before tuning language.

**Project trial checklist:**

- Identify the host process, model boundary, tool boundary, and persistence boundary.
- Write down what state survives a turn, a session, and a restart.
- Define how interruptions, failed tool calls, and partial outputs are represented.
- Verify that runtime behavior can be observed through logs, traces, or status surfaces.

**Possible future skill direction:** A system-design skill for turning an agent idea into a concrete runtime architecture map before implementation.

### 2. Loop and State Machine

**When to use:** Building workflows that require repeated observe-plan-act-verify cycles, multi-step tool use, or resumable task execution.

**Core practice:** Model the agent loop as a state machine with explicit transitions. Avoid relying on vague "keep working" behavior when the workflow has recognizable states such as intake, context gathering, planning, action, verification, handoff, retry, or escalation.

**Project trial checklist:**

- List the named states the agent can occupy.
- Define entry and exit criteria for each state.
- Specify retry limits and escalation conditions.
- Test at least one normal path, one tool-failure path, and one user-interruption path.

**Possible future skill direction:** A workflow-loop skill for designing deterministic agent state machines and recovery paths.

### 3. Prompt Layering and Cache

**When to use:** Maintaining complex prompts that combine global policy, product behavior, project context, session state, and task-specific instructions.

**Core practice:** Separate prompt layers by stability and authority. Keep durable policy, reusable role instructions, retrieved project context, and turn-specific intent distinct so they can be cached, audited, replaced, or invalidated independently.

**Project trial checklist:**

- Identify which prompt material is stable, session-scoped, retrieved, or task-specific.
- Decide what can be cached safely and what must be refreshed.
- Preserve source attribution for retrieved context.
- Test prompt changes by checking whether the intended layer, not an unrelated layer, explains the behavior shift.

**Possible future skill direction:** A prompt-architecture skill for layering instructions and cacheable context without creating brittle monolithic prompts.

### 4. Tool Governance

**When to use:** Giving an agent access to shell commands, file edits, browsers, APIs, MCP servers, or external services.

**Core practice:** Govern tools as capabilities with contracts. For each tool, define allowed use, input constraints, output interpretation, failure handling, and when human confirmation is required.

**Project trial checklist:**

- Inventory the tools the agent can call and the risks each introduces.
- Define read-only, write, network, and destructive-operation boundaries.
- Add verification steps for tool outputs that can be stale, partial, or ambiguous.
- Confirm the agent can explain why a tool was used and what evidence it returned.

**Possible future skill direction:** A tool-governance skill for designing capability policies and verification protocols around agent tools.

### 5. Role Separation

**When to use:** Coordinating agents that plan, implement, review, summarize, route, or operate tools with different authority levels.

**Core practice:** Separate roles by responsibility and trust boundary. A planner should not silently become the reviewer, and a tool operator should not own product judgment unless that role is explicit.

**Project trial checklist:**

- Name each role and its decision authority.
- Define what artifacts pass between roles.
- Decide which roles may modify source files, approve completion, or escalate blockers.
- Verify that review roles evaluate the work against the spec rather than inheriting implementer assumptions.

**Possible future skill direction:** A role-architecture skill for decomposing agent systems into planners, implementers, reviewers, routers, and operators.

### 6. Safety Layers

**When to use:** Designing agents that can change files, execute commands, call external systems, handle sensitive data, or influence user decisions.

**Core practice:** Build safety as layered controls: instruction hierarchy, scoped permissions, tool restrictions, confirmation gates, output checks, and audit trails. Do not depend on one prompt sentence to carry all safety behavior.

**Project trial checklist:**

- Identify sensitive data, destructive operations, and irreversible external actions.
- Add least-privilege defaults for tools and files.
- Define confirmation gates for high-impact operations.
- Log enough context to reconstruct what the agent did and why.

**Possible future skill direction:** A safety-layering skill for mapping operational risk to concrete controls in an agent workflow.

### 7. Context Budget

**When to use:** Working in large repos, long threads, document-heavy tasks, multi-agent workflows, or any project where context pressure changes behavior quality.

**Core practice:** Treat context as a budgeted resource. Prioritize source-of-truth artifacts, compress stable knowledge, summarize handoffs explicitly, and refresh high-risk facts instead of carrying everything forward.

**Project trial checklist:**

- Identify the minimum source-of-truth files or artifacts needed for the task.
- Separate facts that must stay verbatim from facts that can be summarized.
- Track assumptions that need re-checking after compaction, handoff, or long-running work.
- Verify final claims against current files rather than stale thread memory.

**Possible future skill direction:** A context-budgeting skill for deciding what to read, retain, summarize, or refresh during long agent work.

### 8. Productization Lifecycle

**When to use:** Turning repeated agent behavior into reusable methods, repo docs, templates, scripts, plugins, or skills.

**Core practice:** Productize gradually. Start as notes, trial in real projects, identify repeatable triggers and failure modes, then promote only the smallest useful method into a formal artifact.

**Project trial checklist:**

- Capture where the method helped and where it was too vague.
- Record the trigger conditions that reliably identify when to use it.
- Add examples from real projects before generalizing.
- Convert to a skill only after the method has a crisp workflow, boundaries, and verification criteria.

**Possible future skill direction:** A methodology-to-skill graduation skill for deciding when documentation has earned promotion into a reusable system skill.

## Trial Protocol

Before converting any method here into a skill:

1. Use it in at least two materially different projects.
2. Record what changed in the workflow because of the method.
3. Identify failure cases, confusing triggers, and overlap with existing skills.
4. Draft the smallest possible skill candidate.
5. Compare it against `docs/existing-skills-audit.md` to avoid duplicating installed behavior.

Until that happens, these notes remain documentation-level guidance only.
