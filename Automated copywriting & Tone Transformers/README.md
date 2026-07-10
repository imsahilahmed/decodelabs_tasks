# Automated Copywriting & Tone Transformer
**DecodeLabs — Generative AI Industrial Training Kit, Project 2**

A Python application that turns a raw product description into
platform-tailored marketing copy, with full control over the model's
creativity (temperature / top_p) and a concurrent pipeline for
generating many variants at once.

## Architecture (maps to the project slides)

```
CLI / CSV (argparse)         <- slide 14: Input ingestion
        |
prompt_compiler.py           <- slide 6: Master Instruction Template (f-strings)
        |
inference_client.py          <- slide 7: Temperature/top_p control + model call
        |
   /         \
single call   pipeline.py    <- slides 8-11: asyncio + Semaphore + tenacity retry/backoff
   \         /
models.py (Pydantic)         <- slide 16: strict output schema + compliance check
```

- `models.py` — `GeneratedCopy` Pydantic model + per-platform character limits.
- `prompt_compiler.py` — builds the hidden master prompt via f-strings; the
  end user never sees or edits the template itself, only supplies raw facts.
- `inference_client.py` — wraps the Anthropic API call, exposing `temperature`
  and `top_p`, and validates the JSON response against `GeneratedCopy`.
- `pipeline.py` — concurrent batch generation: `asyncio.Semaphore` caps
  in-flight requests at 10, `tenacity` retries failures with exponential
  backoff + jitter, `asyncio.gather` keeps results in input order.
- `run.py` — the CLI (argparse). Two modes: single job, or `--batch` CSV.

> **Provider note:** this build runs on **Groq's free, no-credit-card API
> tier** (OpenAI-compatible endpoint), using the open-source
> `llama-3.3-70b-versatile` model — no cost to build or test this project.
> The slides describe an OpenAI-flavored stack (gpt-4/o1, OpenAI Batch
> API, `openbatch`); Groq's endpoint is OpenAI-compatible, so the same
> `openai` SDK works, just pointed at `https://api.groq.com/openai/v1`.
> The orchestration logic (template compiler, CLI, async+semaphore+retry
> pipeline, Pydantic validation) is identical regardless of provider —
> only `inference_client.py`'s base URL/model name would change to swap
> to OpenAI, Anthropic, or another provider later. That's the point made
> on slide 15: isolating generation logic from the execution environment.
>
> Groq's free tier is rate-limited (not token-budget-limited) — roughly
> 30 requests/minute and a few thousand tokens/minute, shared across your
> whole account. That's why `pipeline.py` caps concurrency at 5 by
> default. If you hit `429` errors, the `tenacity` retry/backoff in
> `pipeline.py` will handle it automatically; just don't fire off huge
> batches back-to-back.

## Setup

```bash
pip install -r requirements.txt
```

Get a free Groq API key (no credit card) at https://console.groq.com/keys, then:

```bash
export GROQ_API_KEY="your-key-here"
```

## Usage

### Single request
```bash
python run.py \
  --product "AquaFlow Bottle" \
  --platform linkedin \
  --tone professional \
  --description "A self-cleaning UV water bottle that keeps water fresh for 24 hours." \
  --temperature 0.3 --top-p 0.9
```

### Preview the compiled prompt without calling the model
```bash
python run.py --product "AquaFlow Bottle" --platform instagram --tone witty \
  --description "..." --dry-run
```

### Bulk/concurrent generation from CSV
```bash
python run.py --batch jobs_sample.csv --out results.json
```

CSV columns: `product_name,platform,tone,description[,temperature,top_p]`

## Supported platforms & constraints
| Platform  | Char limit | Style |
|-----------|-----------|-------|
| linkedin  | 3000      | professional, value-driven |
| instagram | 2200      | punchy, visual, hashtag-friendly |
| email     | 1500      | structured, clear CTA |
| twitter   | 280       | extremely concise |

## Things worth experimenting with (per the slide deck's conclusion)
- Compare `temperature=0.2` vs `0.8` on the **same** product/platform and
  see how brand-voice consistency changes.
- Try a product description that's too long for Twitter's 280-char limit
  and watch `compliance_check` flip to `False`.
- Push `MAX_CONCURRENT_REQUESTS` in `pipeline.py` up/down and observe
  retry/backoff behavior under load.
