"""
inference_client.py
--------------------
"The Parameter Tuning Spectrum" (slide 7) + "Output (Model Client)"
(slide 5). Wraps the generative model call, exposing temperature and
top_p as first-class controls, and parses+validates the JSON response
into the strict Pydantic schema.

Uses Groq's free, no-credit-card API tier (OpenAI-compatible endpoint),
running an open-source model (Llama 3.3 70B by default). This keeps the
project completely free to build and test. The orchestration logic
(templates, CLI, async layer, validation) is provider-agnostic — to
switch to Anthropic or OpenAI later, you'd only touch this file.
"""

from __future__ import annotations
import json
import os

from openai import OpenAI, AsyncOpenAI
from pydantic import ValidationError
from dotenv import load_dotenv
from models import GeneratedCopy
load_dotenv()
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "llama-3.3-70b-versatile"  # free-tier model on Groq; swap for any model in your Groq console

_client = OpenAI(api_key=os.environ.get("GROQ_API_KEY", "not-set"), base_url=GROQ_BASE_URL)
_async_client = AsyncOpenAI(api_key=os.environ.get("GROQ_API_KEY", "not-set"), base_url=GROQ_BASE_URL)


def _extract_json(text: str) -> dict:
    """Defensively strip markdown fences if the model adds them anyway."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def generate_copy_sync(
    prompt: str,
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 500,
) -> GeneratedCopy:
    """
    Single, blocking call to the model. Used by the CLI's simple/single
    mode (no concurrency needed for one request).
    """
    response = _client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = response.choices[0].message.content or ""

    try:
        data = _extract_json(raw_text)
        copy = GeneratedCopy(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise RuntimeError(
            f"Model output failed schema validation: {e}\nRaw output:\n{raw_text}"
        ) from e

    copy.check_compliance()
    return copy


async def generate_copy_async(
    prompt: str,
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 500,
) -> GeneratedCopy:
    """
    Async variant used by the concurrent batch pipeline (see pipeline.py).
    AsyncOpenAI (pointed at Groq) gives us a non-blocking `await` point,
    exactly matching "Asynchronous Python Foundations" (slide 9). Note:
    Groq's free tier RPM/TPM caps mean the semaphore in pipeline.py is
    even more important here than on a paid tier — keep MAX_CONCURRENT
    modest (e.g. 5) to avoid 429s.
    """
    response = await _async_client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = response.choices[0].message.content or ""

    data = _extract_json(raw_text)  # let exceptions bubble up to tenacity retry wrapper
    copy = GeneratedCopy(**data)
    copy.check_compliance()
    return copy
