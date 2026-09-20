# Volcengine Ark Seedream

Use the `ark` profile for Volcengine Ark Seedream generation. The preset configures:

```dotenv
IMAGEGEN_PROVIDER=ark
IMAGEGEN_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
IMAGEGEN_MODEL=doubao-seedream-5-0-pro-260628
IMAGEGEN_GENERATIONS_PATH=/images/generations
```

Ordinary users do not need to edit these values. On macOS, double-click `scripts/setup-seedream.command`, paste the Key once, and wait for “配置完成”.

The model ID is configurable because Ark deployments and entitlements can differ. Override it during setup when the user's current Ark console or working application uses another endpoint ID:

```bash
python3 <skill-dir>/scripts/configure.py ark \
  --model <current-ark-endpoint-or-model-id> \
  --env-file .env
```

## Request mapping

The adapter sends:

- `Authorization: Bearer <key>`;
- `Content-Type: application/json`;
- a unique `Idempotency-Key` unless one is supplied;
- `model`, `prompt`, optional `size`, `response_format: b64_json`, `output_format: png`, and `watermark: false`;
- ordered reference images as Data URLs in the JSON `image` array.

Ark references stay on `/images/generations`; the adapter never sends them to `/images/edits`. The local request record stores source paths, sizes, and SHA-256 values while omitting the embedded Data URL bytes.

The current Ark profile supports one output per request. Use separate authorized requests for additional outputs rather than assuming `n` compatibility. Provider-specific documented options such as `sequential_image_generation` can be supplied with `--extra-file`.

## Example

```bash
python3 <skill-dir>/scripts/generate_image.py --check \
  --prompt-file prompt.txt \
  --reference /absolute/path/product.png \
  --size 1024x1024 \
  --name seedream-product

python3 <skill-dir>/scripts/generate_image.py --execute \
  --prompt-file prompt.txt \
  --reference /absolute/path/product.png \
  --size 1024x1024 \
  --name seedream-product \
  --output-dir generated-images
```

The check is local. Execution can consume quota and uploads the prompt and every reference image to Ark, so it requires authorization for that call.
