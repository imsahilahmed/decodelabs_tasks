"""
providers.py
------------
Adapters for each text-to-image engine. Each adapter knows how to:
  1. build the provider-specific JSON payload from generic params
  2. call the provider's endpoint
  3. return either raw image bytes, a streaming response, or a URL

This keeps generator.py (the pipeline / orchestration layer) provider-agnostic.
"""

import base64
import io
import os
import random
import time

import requests

# ---------------------------------------------------------------------------
# Aspect ratio -> exact resolution map (per "Translating Aspect Ratios into
# Exact Pixel Payloads" — passing unsupported dimensions causes an API
# handshake failure, so we always map to a known-good resolution).
# ---------------------------------------------------------------------------
ASPECT_RATIO_MAP = {
    "16:9": (1344, 768),
    "1:1": (1024, 1024),
    "9:16": (768, 1344),
}

CONNECT_TIMEOUT = 3.05   # seconds — fail fast on unreachable hosts
READ_TIMEOUT = 60        # seconds — diffusion inference is slow


class ProviderError(Exception):
    """Base class for provider-level failures."""


class ContentPolicyError(ProviderError):
    """Raised when the input prompt is rejected by a pre-generation safety gate."""


class ModerationBlockedError(ProviderError):
    """Raised when a generated image is withheld by a post-generation safety gate."""


class TransientAPIError(ProviderError):
    """Raised for retryable failures (429 / 5xx / timeouts)."""


def resolve_resolution(aspect_ratio: str):
    if aspect_ratio not in ASPECT_RATIO_MAP:
        raise ValueError(
            f"Unsupported aspect ratio '{aspect_ratio}'. "
            f"Supported: {list(ASPECT_RATIO_MAP)}"
        )
    return ASPECT_RATIO_MAP[aspect_ratio]


# ---------------------------------------------------------------------------
# Mock provider — lets the whole pipeline run end-to-end with no API key.
# Simulates latency and occasionally simulates a safety rejection or a
# truncated stream so the resilience logic actually has something to do.
# ---------------------------------------------------------------------------
class MockProvider:
    name = "mock"

    def generate(self, prompt: str, width: int, height: int, style: str | None):
        time.sleep(random.uniform(0.6, 1.4))  # simulate GPU inference

        lowered = prompt.lower()
        if any(w in lowered for w in ("nude", "weapon", "gore")):
            raise ContentPolicyError("sentinel_block: prompt failed pre-generation review")

        # Build a simple gradient placeholder so there's a real image to show.
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)
        c1 = _hash_color(prompt)
        c2 = _hash_color(style or "default")
        for y in range(height):
            t = y / max(height - 1, 1)
            r = int(c1[0] * (1 - t) + c2[0] * t)
            g = int(c1[1] * (1 - t) + c2[1] * t)
            b = int(c1[2] * (1 - t) + c2[2] * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        draw.text((20, 20), f"MOCK RENDER\n{prompt[:60]}", fill=(255, 255, 255))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()

        # Occasionally simulate a mid-stream network drop to exercise the
        # integrity-verification stage.
        if random.random() < 0.12:
            data = data[: len(data) // 2]

        return {"mode": "bytes", "data": data}


# ---------------------------------------------------------------------------
# OpenAI gpt-image-1 (successor to the retired DALL-E 3). Returns Base64 JSON.
# ---------------------------------------------------------------------------
class OpenAIProvider:
    name = "openai"
    ENDPOINT = "https://api.openai.com/v1/images/generations"
    MAX_PROMPT_CHARS = 4000

    def generate(self, prompt: str, width: int, height: int, style: str | None):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("OPENAI_API_KEY is not set")

        if len(prompt) > self.MAX_PROMPT_CHARS:
            raise ValueError(f"Prompt exceeds {self.MAX_PROMPT_CHARS} character limit for gpt-image")

        payload = {
            "model": "gpt-image-1",
            "prompt": _apply_style(prompt, style),
            "size": f"{width}x{height}",
            "n": 1,
        }
        headers = {"Authorization": f"Bearer {api_key}"}

        resp = requests.post(
            self.ENDPOINT,
            json=payload,
            headers=headers,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        _raise_for_gate_errors(resp)

        body = resp.json()
        b64 = body["data"][0]["b64_json"]
        return {"mode": "bytes", "data": base64.b64decode(b64)}


# ---------------------------------------------------------------------------
# Stability AI — Stable Image Core (REST v2beta). Returns raw image bytes
# or Base64 JSON depending on Accept header; we request raw bytes so we can
# demonstrate true chunked streaming.
# ---------------------------------------------------------------------------
class StabilityProvider:
    name = "stability"
    ENDPOINT = "https://api.stability.ai/v2beta/stable-image/generate/core"
    MAX_PROMPT_CHARS = 10000

    def generate(self, prompt: str, width: int, height: int, style: str | None):
        api_key = os.environ.get("STABILITY_API_KEY")
        if not api_key:
            raise ProviderError("STABILITY_API_KEY is not set")

        if len(prompt) > self.MAX_PROMPT_CHARS:
            raise ValueError(f"Prompt exceeds {self.MAX_PROMPT_CHARS} character limit for Stability")

        aspect_ratio = _dims_to_aspect(width, height)
        data = {
            "prompt": _apply_style(prompt, style),
            "aspect_ratio": aspect_ratio,
            "output_format": "png",
        }
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "image/*"}

        resp = requests.post(
            self.ENDPOINT,
            data=data,
            files={"none": ""},
            headers=headers,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            stream=True,
        )
        _raise_for_gate_errors(resp)
        return {"mode": "stream", "response": resp}


# ---------------------------------------------------------------------------
# Pollinations.ai — genuinely free, no signup, no API key, open-source
# (Berlin-based). Serves the Flux model over a plain HTTP GET and returns
# raw image bytes, which we stream through the same chunked-download path
# as Stability. This is the recommended default for learners who don't
# have a paid key yet.
# ---------------------------------------------------------------------------
class PollinationsProvider:
    name = "pollinations"
    ENDPOINT = "https://image.pollinations.ai/prompt/{prompt}"
    MAX_PROMPT_CHARS = 2000

    def generate(self, prompt: str, width: int, height: int, style: str | None):
        if len(prompt) > self.MAX_PROMPT_CHARS:
            raise ValueError(f"Prompt exceeds {self.MAX_PROMPT_CHARS} character limit for Pollinations")

        import urllib.parse

        full_prompt = _apply_style(prompt, style)
        url = self.ENDPOINT.format(prompt=urllib.parse.quote(full_prompt))
        params = {
            "width": width,
            "height": height,
            "nologo": "true",
            "model": "flux",
            # random seed so repeat prompts don't just hit a cache and
            # return the identical image every time
            "seed": random.randint(1, 999999),
        }

        resp = requests.get(
            url,
            params=params,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            stream=True,
        )
        _raise_for_gate_errors(resp)
        return {"mode": "stream", "response": resp}


def _apply_style(prompt: str, style: str | None) -> str:
    if not style or style == "none":
        return prompt
    presets = {
        "cyberpunk": "cyberpunk aesthetic, neon lighting, futuristic, high contrast",
        "minimalism": "minimalist, clean lines, negative space, muted palette",
        "photorealistic": "photorealistic, natural lighting, high detail, 85mm lens",
        "watercolor": "watercolor painting, soft edges, paper texture, pastel tones",
    }
    suffix = presets.get(style, style)
    return f"{prompt}, {suffix}"


def _dims_to_aspect(width: int, height: int) -> str:
    for ratio, (w, h) in ASPECT_RATIO_MAP.items():
        if (w, h) == (width, height):
            return ratio
    return "1:1"


def _raise_for_gate_errors(resp: requests.Response):
    if resp.status_code == 200:
        return
    if resp.status_code in (400, 403) and _looks_like_content_policy(resp):
        raise ContentPolicyError(f"content_policy_violation ({resp.status_code})")
    if resp.status_code in (429, 500, 502, 503, 504):
        raise TransientAPIError(f"HTTP {resp.status_code} from provider")
    raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:200]}")


def _looks_like_content_policy(resp: requests.Response) -> bool:
    try:
        text = resp.text.lower()
    except Exception:
        return False
    return any(k in text for k in ("content_policy", "moderation", "safety"))


def _hash_color(text: str):
    h = abs(hash(text))
    return (h % 200 + 30, (h // 7) % 200 + 30, (h // 13) % 200 + 30)


PROVIDERS = {
    "mock": MockProvider(),
    "openai": OpenAIProvider(),
    "stability": StabilityProvider(),
    "pollinations": PollinationsProvider(),
}
