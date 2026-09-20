---
name: openai-compatible-imagegen
description: Generate or edit images through OpenAI-compatible Images APIs or Volcengine Ark Seedream using a user-configured API key and base URL. Use from any Agent Skills-compatible agent for direct prompt-to-image or reference-image generation with traceable local results; do not use for full ecommerce Listing production.
---

# OpenAI-Compatible ImageGen

Generate an image through the user's configured provider and keep the result, request settings, and source-image fingerprints together in a local run directory. This skill uses ordinary `SKILL.md` instructions and local scripts; it does not depend on Codex-only APIs. An agent must support Agent Skills or be able to read this folder and run its scripts.

## Installation ownership

The receiving agent owns installation. If this folder is supplied as an uninstalled package, read [INSTALL.md](INSTALL.md), use the current agent product's supported Skill/import mechanism, and verify discovery. Do not ask a non-technical user to locate a Skills directory, copy files, run installation commands, or choose runtime dependencies.

## First-time setup

After the agent has installed the Skill, keep setup non-technical. Do not ask the user to paste a Key into chat or explain environment variables unless they ask.

For a Windows user, direct them to double-click `scripts/setup-seedream.cmd`. It uses Windows PowerShell to supply the Ark URL and Seedream model automatically; the user only pastes the Key into the private hidden prompt once. When UI access is available, open the launcher for them instead of giving terminal instructions.

For macOS, use `scripts/setup-seedream.command`. For other systems, run the guided Python setup:

```text
python3 <skill-dir>/scripts/configure.py ark
```

The setup writes a private per-user configuration that later runs find automatically. Never print, copy into prompts, commit, or return the Key. Read [configuration.md](references/configuration.md) only for custom providers or advanced settings. For Ark protocol details, read [ark-seedream.md](references/ark-seedream.md).

## Generate

1. Ask what image the user wants. Confirm any reference images because they will be uploaded to the configured provider.
2. Prepare a prompt file and output path for the user. Do not make them assemble commands or configuration fields; a prompt file keeps long prompts out of process listings.
3. On Windows, use the included PowerShell engine. It needs no Python, Node.js, package manager, or third-party runtime. Validate locally first; this does not call the provider:

```text
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File <skill-dir>\scripts\generate-image.ps1 -Check -PromptFile prompt.txt -Name concept-01
```

4. Execute only when the current request authorizes the external generation and any reference-image upload. Setup, inspection, or dry-run requests do not authorize a paid call.

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File <skill-dir>\scripts\generate-image.ps1 `
  -Execute -PromptFile prompt.txt -Name concept-01 -OutputDir generated-images
```

For image-to-image work on Windows, add `-Reference C:\absolute\path\image.png`; join multiple paths with `|`. The PowerShell engine targets Ark Seedream. On non-Windows systems, use `scripts/generate_image.py` for Ark or the generic OpenAI-compatible profile. Ark references are encoded as Data URLs in the JSON `image` array and sent to `/images/generations`.

## Deliver

Report the exact run directory and generated image paths. Each successful run contains:

- `request.json`: endpoint, payload, and reference-image paths/hashes, without authorization headers;
- `response.json`: provider response with URL query strings redacted;
- `run.json`: status, timing, and output hashes;
- numbered image files.

Failed executed runs retain `request.json`, `run.json`, and `error.json`. A local `--check` proves configuration and input shape only; it does not prove provider compatibility or a successful paid generation. Inspect generated images before claiming visual success.

## Boundaries

- This skill handles one direct API generation command, including the verified Ark/Seedream request shape, but not Listing strategy, product-fact control, image-set QA, publishing, or object-storage upload.
- Do not invent a model ID. Use the user's configuration or a provider-documented value.
- Do not silently retry uncertain timeouts or 5xx responses because the first request may still be billable.
- Keep concurrency and multi-round orchestration outside this skill unless a later real use case demonstrates that need.
