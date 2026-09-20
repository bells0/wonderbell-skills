---
name: openai-compatible-imagegen
description: Generate or edit images through an OpenAI-compatible Images API using a user-configured API key and base URL. Use for direct prompt-to-image or reference-image generation that should be saved locally with traceable request records; do not use for provider-specific non-compatible APIs or full ecommerce Listing production.
---

# OpenAI-Compatible ImageGen

Generate an image through the user's configured provider and keep the result, request settings, and source-image fingerprints together in a local run directory. The included script uses only the Python standard library.

## Configure

Before the first run, read [configuration.md](references/configuration.md). Reuse an existing configuration without asking the user to reveal the key. Never print, copy into prompts, commit, or return the key.

The minimum private configuration is:

```dotenv
IMAGEGEN_API_KEY=your-key
IMAGEGEN_BASE_URL=https://provider.example/v1
```

Users may copy [`.env.example`](.env.example) to a private working-directory `.env`. Set `IMAGEGEN_MODEL` when the provider requires an explicit image model. The script also accepts `OPENAI_API_KEY` and `OPENAI_BASE_URL` as fallbacks.

## Generate

1. Confirm the intended image, output location, and any reference images. Treat reference files as material that will be uploaded to the configured external provider.
2. Put the final prompt in a UTF-8 text file. Prefer `--prompt-file` so long prompts do not leak into shell history or process listings.
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

For image-to-image work, add one or more `--reference /absolute/path/to/image.png`. `--mode auto` selects the edits endpoint when references are present and the generations endpoint otherwise. Use `--model`, `--size`, `--quality`, `--n`, or `--extra-file` only when the selected provider supports them.

## Deliver

Report the exact run directory and generated image paths. Each successful run contains:

- `request.json`: endpoint, payload, and reference-image paths/hashes, without authorization headers;
- `response.json`: provider response with URL query strings redacted;
- `run.json`: status, timing, and output hashes;
- numbered image files.

Failed executed runs retain `request.json`, `run.json`, and `error.json`. A local `--check` proves configuration and input shape only; it does not prove provider compatibility or a successful paid generation. Inspect generated images before claiming visual success.

## Boundaries

- This skill handles one direct API generation command, not Listing strategy, product-fact control, image-set QA, publishing, or object-storage upload.
- Do not invent a model ID. Use the user's configuration or a provider-documented value.
- Do not silently retry uncertain timeouts or 5xx responses because the first request may still be billable.
- Keep concurrency and multi-round orchestration outside this skill unless a later real use case demonstrates that need.
