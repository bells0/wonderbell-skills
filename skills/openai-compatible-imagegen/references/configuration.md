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

For a non-technical Windows user, double-click:

```text
scripts\setup-seedream.cmd
```

The Windows launcher uses the system PowerShell. It asks only for the Key and confirms when setup is complete. The Key is hidden while pasted, saved under `%APPDATA%\WonderbellImagegen\.env`, and restricted to the current Windows account. Later image-generation runs find it automatically.

On macOS, double-click `scripts/setup-seedream.command`. On other systems, the configurator supplies the known base URL and model ID; the only hidden prompt is the Key:

```bash
python3 <skill-dir>/scripts/configure.py ark
```

For automation, place the Key in a temporary environment variable and name that variable without putting the Key on the command line:

```bash
python3 <skill-dir>/scripts/configure.py ark \
  --api-key-env MY_PRIVATE_ARK_KEY \
  --env-file .env
```

The Python configurator writes atomically, preserves unrelated entries, and changes the target file to mode `0600`. The Windows launcher applies a file ACL for the current account. Neither copies a Key from another application or database automatically. Advanced users may still pass `--env-file` to choose another location.

## Agent compatibility

The portable contract is this `SKILL.md` folder plus its local scripts. It does not call Codex-specific tools. The receiving agent must perform installation as described in [INSTALL.md](../INSTALL.md); the business user should not manage Skill directories or installation commands. Agents that implement the Agent Skills convention can load it directly; other agents can use it only if their product supports importing a skill folder or equivalent instructions. Windows generation uses built-in Windows PowerShell and needs no Python or Node.js. The Python adapter remains available for non-Windows systems and generic providers.

## Common commands

Windows text-to-image check and execution:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File <skill-dir>\scripts\generate-image.ps1 `
  -Check -PromptFile prompt.txt -Name hero

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File <skill-dir>\scripts\generate-image.ps1 `
  -Execute -PromptFile prompt.txt -Name hero -OutputDir generated-images
```

Non-Windows or generic-provider check and execution:

```bash
<python> <skill-dir>/scripts/generate_image.py --check \
  --prompt-file prompt.txt --name hero

<python> <skill-dir>/scripts/generate_image.py --execute \
  --prompt-file prompt.txt --name hero --output-dir generated-images
```

Windows reference-image generation:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File <skill-dir>\scripts\generate-image.ps1 `
  -Execute -PromptFile prompt.txt -Reference "C:\images\front.png|C:\images\detail.jpg" `
  -Name product-scene -OutputDir generated-images
```

Non-Windows or generic-provider reference-image generation:

```bash
<python> <skill-dir>/scripts/generate_image.py --execute \
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
