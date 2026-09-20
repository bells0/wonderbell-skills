# Configuration

The adapter supports two profiles:

- `openai-compatible`: bearer authentication, JSON requests for `/images/generations`, multipart form requests for `/images/edits`, and base64 or URL results.
- `ark`: Volcengine Ark Seedream requests using JSON `/images/generations`, including Data URL reference images, and base64 or URL results.

## Environment

Create a local `.env` outside Git, or export the variables in the process environment:

```dotenv
IMAGEGEN_PROVIDER=openai-compatible
IMAGEGEN_API_KEY=
IMAGEGEN_BASE_URL=

# Optional provider settings
IMAGEGEN_MODEL=
IMAGEGEN_TIMEOUT_SECONDS=180
IMAGEGEN_GENERATIONS_PATH=/images/generations
IMAGEGEN_EDITS_PATH=/images/edits
IMAGEGEN_REFERENCE_FIELD=image[]
```

`IMAGEGEN_BASE_URL` is the API root, commonly ending in `/v1`; do not append `/images/generations`. HTTPS is required except for localhost testing. The base URL cannot contain credentials, a query string, or a fragment.

The script uses `IMAGEGEN_*` values first and falls back to `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_IMAGE_MODEL`. Pass a non-default file with `--env-file /path/to/.env`.

## One-step configuration

For a non-technical macOS user, double-click:

```text
scripts/setup-seedream.command
```

The window asks only for the Key and confirms when setup is complete. The Key is hidden while pasted. The configuration is stored at `~/.config/wonderbell-imagegen/.env`, and later image-generation runs find it automatically.

For other systems, the configurator supplies the known base URL and model ID; the only hidden prompt is the Key:

```bash
python3 <skill-dir>/scripts/configure.py ark
```

For automation, place the Key in a temporary environment variable and name that variable without putting the Key on the command line:

```bash
python3 <skill-dir>/scripts/configure.py ark \
  --api-key-env MY_PRIVATE_ARK_KEY \
  --env-file .env
```

The configurator writes atomically, preserves unrelated entries, and changes the target file to mode `0600`. It does not copy a Key from another application or database automatically. Advanced users may still pass `--env-file` to choose another location.

## Common commands

Text-to-image check and execution:

```bash
python3 <skill-dir>/scripts/generate_image.py --check \
  --prompt-file prompt.txt --name hero

python3 <skill-dir>/scripts/generate_image.py --execute \
  --prompt-file prompt.txt --name hero --output-dir generated-images
```

Reference-image generation:

```bash
python3 <skill-dir>/scripts/generate_image.py --execute \
  --prompt-file prompt.txt \
  --reference /absolute/path/product-front.png \
  --reference /absolute/path/product-detail.jpg \
  --name product-scene \
  --output-dir generated-images
```

Provider-specific parameters belong in a JSON object file:

```json
{
  "moderation": "auto"
}
```

Pass it with `--extra-file provider-options.json`. The file cannot replace protected fields such as `prompt`, `model`, or `n`.

## Compatibility limits

OpenAI-compatible does not mean every provider implements every parameter or the same edits field name. Change `IMAGEGEN_REFERENCE_FIELD` or endpoint paths only from current provider documentation. A successful `--check` validates local input and configuration, not the remote provider's model entitlement, quota, accepted parameters, or billing.

The adapter sends `Authorization: Bearer <key>`. APIs requiring query-parameter keys, vendor-specific signing, asynchronous polling, or a different response schema need a separate adapter rather than putting credentials into the base URL.
