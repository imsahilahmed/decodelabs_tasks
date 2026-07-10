"""
generator.py
------------
Orchestrates the six-stage pipeline described in the "Complete Project 3
Blueprint":

  1. Prompt Payload Formulation   (aspect ratio -> exact resolution)
  2. Network API Gateway          (dual timeout: 3.05s connect / 60s read)
  3. Security & Moderation Gates  (input + output rejection handling)
  4. Transport Protocol           (memory-safe chunked binary streaming)
  5. Integrity Verification       (forced pixel-level decode)
  6. Automated Quality Assurance  (lightweight aesthetic heuristic)

Every stage appends a structured entry to a `log` list that the frontend
replays to animate the pipeline diagram.
"""

import os
import random
import time
import uuid

from PIL import Image, UnidentifiedImageError

from providers import (
    PROVIDERS,
    ContentPolicyError,
    ModerationBlockedError,
    ProviderError,
    TransientAPIError,
    resolve_resolution,
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
CHUNK_SIZE = 65536  # 64 KiB — matches the deck's "iter_content(chunk_size=65536)" rule
MAX_RETRIES = 3
BASE_BACKOFF = 2.0  # seconds


class PipelineError(Exception):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.message = message


class StageLog:
    def __init__(self):
        self.entries = []
        self._t0 = time.time()

    def add(self, stage: str, status: str, detail: str = ""):
        self.entries.append(
            {
                "stage": stage,
                "status": status,  # "ok" | "retry" | "error"
                "detail": detail,
                "t": round(time.time() - self._t0, 2),
            }
        )


def run_pipeline(prompt: str, aspect_ratio: str, style: str, provider_name: str) -> dict:
    log = StageLog()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---- Stage 1: Prompt Payload Formulation --------------------------
    try:
        width, height = resolve_resolution(aspect_ratio)
    except ValueError as e:
        log.add("payload", "error", str(e))
        raise PipelineError("payload", str(e)) from e
    log.add("payload", "ok", f"{width}x{height} ({aspect_ratio}) via {provider_name}")

    provider = PROVIDERS.get(provider_name)
    if provider is None:
        raise PipelineError("payload", f"Unknown provider '{provider_name}'")

    # ---- Stage 2 + 3: Network Gateway + Security Gates (with retry) ---
    result = None
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = provider.generate(prompt, width, height, style)
            log.add("network", "ok", f"attempt {attempt} succeeded")
            break
        except ContentPolicyError as e:
            # Gate 1 (pre-generation): zero compute cost, do not retry.
            log.add("security", "error", f"Gate 1 rejection: {e}")
            raise PipelineError("security", str(e)) from e
        except ModerationBlockedError as e:
            # Gate 2 (post-generation): compute already spent, do not retry.
            log.add("security", "error", f"Gate 2 rejection: {e}")
            raise PipelineError("security", str(e)) from e
        except TransientAPIError as e:
            last_error = e
            log.add("network", "retry", f"attempt {attempt} failed: {e}")
        except ProviderError as e:
            last_error = e
            log.add("network", "error", str(e))
            raise PipelineError("network", str(e)) from e

        if attempt < MAX_RETRIES:
            delay = BASE_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0, 1)  # backoff + jitter
            time.sleep(min(delay, 4))  # capped for demo responsiveness

    if result is None:
        log.add("network", "error", f"exhausted {MAX_RETRIES} attempts")
        raise PipelineError("network", f"Failed after {MAX_RETRIES} attempts: {last_error}")

    log.add("security", "ok", "passed both moderation gates")

    # ---- Stage 4: Transport Protocol (memory-safe streaming) ----------
    file_id = uuid.uuid4().hex[:12]
    file_path = os.path.join(OUTPUT_DIR, f"{file_id}.png")

    try:
        total_bytes = _stream_to_disk(result, file_path)
    except Exception as e:
        log.add("transport", "error", str(e))
        raise PipelineError("transport", f"Streaming write failed: {e}") from e
    log.add("transport", "ok", f"{total_bytes / 1024:.1f} KiB written in {CHUNK_SIZE // 1024} KiB chunks")

    # ---- Stage 5: Integrity Verification -------------------------------
    try:
        with Image.open(file_path) as im:
            im.load()  # forces full pixel-level decode, not just header read
            dims = im.size
    except (UnidentifiedImageError, OSError) as e:
        os.remove(file_path)
        log.add("integrity", "error", f"corrupted/truncated stream: {e}")
        raise PipelineError("integrity", f"Downloaded asset failed integrity check: {e}") from e
    log.add("integrity", "ok", f"verified {dims[0]}x{dims[1]} — full decode successful")

    # ---- Stage 6: Automated QA (lightweight heuristic stand-in) --------
    score = _aesthetic_heuristic(file_path)
    qa_status = "ok" if score >= 7.0 else "error"
    log.add("qa", qa_status, f"aesthetic score {score}/10.0 (threshold 7.0)")
    if qa_status == "error":
        # In this demo we surface it rather than silently discarding, so the
        # learner can see the gate fire.
        pass

    return {
        "file_id": file_id,
        "filename": f"{file_id}.png",
        "width": dims[0],
        "height": dims[1],
        "requested_width": width,
        "requested_height": height,
        "qa_score": score,
        "log": log.entries,
    }


def _stream_to_disk(result: dict, file_path: str) -> int:
    total = 0
    if result["mode"] == "bytes":
        data = result["data"]
        with open(file_path, "wb") as f:
            for i in range(0, len(data), CHUNK_SIZE):
                chunk = data[i : i + CHUNK_SIZE]
                f.write(chunk)
                total += len(chunk)
        return total

    if result["mode"] == "stream":
        resp = result["response"]
        with open(file_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
        return total

    raise ValueError(f"Unknown provider result mode: {result['mode']}")


def _aesthetic_heuristic(file_path: str) -> float:
    """
    Stand-in for the CLIP ViT-L/14 aesthetic classifier described in the
    deck. Real deployments would embed the image and score it with a
    trained linear head; here we use a cheap contrast/variance proxy so the
    QA stage has a real (if simplified) signal to act on.
    """
    with Image.open(file_path) as im:
        im = im.convert("L").resize((64, 64))
        pixels = list(im.getdata())
    mean = sum(pixels) / len(pixels)
    variance = sum((p - mean) ** 2 for p in pixels) / len(pixels)
    normalized = min(variance / 4000, 1.0) * 10
    return round(max(normalized, 3.0), 1)
