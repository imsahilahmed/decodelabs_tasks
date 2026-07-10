# Multimodal Image Generation Studio

Project 3 (DecodeLabs Generative AI Industrial Training Kit) — a text-to-image
pipeline that turns natural language prompts into digital artwork, with
production-grade handling of timeouts, retries, safety gates, streaming
downloads, and integrity verification.

## What it does

| Stage | File | What it implements |
|---|---|---|
| 1. Prompt Payload | `providers.py` | Maps `16:9 / 1:1 / 9:16` to exact pixel resolutions before sending anything over the wire |
| 2. Network Gateway | `providers.py`, `generator.py` | Dual timeout (`connect=3.05s`, `read=60s`) + exponential backoff with jitter on `429/5xx` |
| 3. Security Gates | `providers.py`, `generator.py` | Distinguishes pre-generation (`ContentPolicyError`, zero cost) from post-generation (`ModerationBlockedError`, compute already spent) rejections |
| 4. Transport | `generator.py` | Streams the response in 64 KiB chunks straight to disk — never loads the whole image into RAM |
| 5. Integrity | `generator.py` | Forces `Image.open().load()` so a truncated download raises immediately instead of silently saving a corrupt file |
| 6. QA | `generator.py` | Lightweight aesthetic-score heuristic standing in for a CLIP-based classifier gate |

## Run it — real images, no API key, no cost

```bash
cd studio
pip install -r requirements.txt --break-system-packages
python app.py
```

Open `http://localhost:5050`. The engine dropdown defaults to **Pollinations**
— an open-source, no-signup, no-API-key text-to-image service (Berlin-based,
runs the Flux model) that's genuinely free. Type a real prompt like "a lion
in a cage" and click **RUN PIPELINE** — you'll get an actual generated image,
streamed through the same chunked-download and integrity-verification path
described below. No `.env`, no billing, no credit card.

Pollinations has no official uptime SLA and can be slower or rate-limited
under heavy community load, which is exactly the kind of real-world
flakiness the retry/backoff logic in `generator.py` is built to absorb.

### Offline / no-network testing: Mock engine

Switch the dropdown to **Mock** to render a local gradient placeholder
instead of calling any network at all. It occasionally simulates a truncated
download (~12% of the time) so you can watch the integrity-verification
stage actually catch something, and occasionally rejects prompts containing
obviously unsafe words so you can see the security-gate path fire too. Good
for demoing the pipeline with zero internet dependency.

## Going live with a paid engine (OpenAI / Stability)

```bash
cp .env.example .env
# then edit .env and add ONE of:
#   OPENAI_API_KEY=sk-...
#   STABILITY_API_KEY=sk-...
```

Load the `.env` file however you prefer (e.g. `export $(cat .env | xargs)`
before running, or add `python-dotenv` if you want it automatic), then pick
**gpt-image-1** or **Stable Image Core** in the UI dropdown.

- **gpt-image-1** (OpenAI): prompt limit 4,000 chars, returns Base64 JSON.
- **Stable Image Core** (Stability AI): prompt limit 10,000 chars, returns
  raw image bytes — this is the path that exercises true chunked streaming.

## Extending it

Ideas straight from the deck's "Conclusion" slide:
- Add more style presets in `providers.py::_apply_style`.
- Swap the QA heuristic for a real CLIP ViT-L/14 aesthetic scorer.
- Add a batch mode (`generation count` parameter) that fans out multiple
  requests and shows a grid of results.
- Wire `Enterprise Scaling` targets (Unreal Engine / Blender / Polycam) by
  adding an "export" adapter that pushes the verified PNG somewhere else.

## Project layout

```
studio/
  app.py            Flask routes
  generator.py      Pipeline orchestration (retries, streaming, integrity, QA)
  providers.py      Provider adapters (mock / openai / stability) + aspect-ratio map
  templates/
    index.html      UI shell
  static/
    style.css       Blueprint-styled theme
    app.js          Frontend logic + pipeline animation
  outputs/          Generated PNGs land here
```
