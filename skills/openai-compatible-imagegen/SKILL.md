---
name: openai-compatible-imagegen
description: Generate or edit images through OpenAI-compatible Images APIs or Volcengine Ark Seedream using a user-configured API key and base URL. Use for direct prompt-to-image or reference-image generation that should be saved locally with traceable request records; do not use for full ecommerce Listing production.
---

# OpenAI-Compatible ImageGen

Generate an image through the user's configured provider and keep the result, request settings, and source-image fingerprints together in a local run directory. The included script uses only the Python standard library.

## First-time setup

Keep setup non-technical. Do not ask the user to paste a Key into chat or explain environment variables unless they ask.

For a macOS user, direct them to double-click `scripts/setup-seedream.command`. It supplies the Ark URL and Seedream model automatically; the user only pastes the Key into the private hidden prompt once. When UI access is available, open the launcher for them instead of giving terminal instructions.

For other systems, run this guided setup:

```text
python3 <skill-dir>/scripts/configure.py ark
```

The setup writes a private per-user configuration that later runs find automatically. Never print, copy into prompts, commit, or return the Key. Read [configuration.md](references/configuration.md) only for custom providers or advanced settings. For Ark protocol details, read [ark-seedream.md](references/ark-seedream.md).

## Generate

1. Ask what image the user wants. Confirm any reference images because they will be uploaded to the configured provider.
2. Prepare the prompt and output path for the user. Do not make them assemble commands or configuration fields. Prefer `--prompt-file` so long prompts do not leak into shell history or process listings.
3. Validate locally first. This does not call the provider:

```bash
python3 <skill-dir>/scripts/generate_image.py \
  --check \
  --prompt-file prompt.txt \
  --name concept-01
```

4. Execute only when the current request authorizes the external generation and any reference-image upload. Setup, inspection, or dry-run requests do not authorize a paid call.

```bash
python3 <skill-dir>/scripts/generate_image.py \
  --execute \
  --prompt-file prompt.txt \
  --name concept-01 \
  --output-dir generated-images
```

For image-to-image work, add one or more `--reference /absolute/path/to/image.png`. With `openai-compatible`, `--mode auto` selects the edits endpoint for references. With `ark`, references are encoded as Data URLs in the JSON `image` array and sent to `/images/generations`, matching Seedream's working protocol. Use `--model`, `--size`, `--quality`, `--n`, or `--extra-file` only when the selected provider supports them.

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
