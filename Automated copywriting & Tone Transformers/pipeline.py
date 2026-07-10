"""
pipeline.py
-----------
"The Scaling Dilemma" (slide 8), "Concurrency Patterns" (slide 10),
and "Building Resilience Against Rate Limits" (slide 11).

This is the real-time bulk pipeline: generate many copy variants
concurrently (e.g. same product across LinkedIn + Instagram + Email
+ multiple tones at once) without getting hit with HTTP 429s.

- asyncio.Semaphore caps concurrent in-flight requests ("The Semaphore Gate").
- tenacity retries transient failures with exponential backoff + jitter
  ("The Activation Curve").
- asyncio.gather preserves result order (matches input index) — chosen
  here over as_completed because batch jobs need deterministic ordering
  for downstream reporting/export.
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import List

from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type

from inference_client import generate_copy_async
from models import GeneratedCopy
from prompt_compiler import compile_prompt

MAX_CONCURRENT_REQUESTS = 5  # the "Semaphore Gate" limit from slide 11
# Lowered for Groq's free tier (~30 requests/min, ~6000 tokens/min org-wide).
# Bump this up if you're on a paid/Developer tier with higher rate limits.


@dataclass
class CopyJob:
    product_name: str
    platform: str
    tone: str
    product_description: str
    temperature: float = 0.7
    top_p: float = 0.95


@retry(
    wait=wait_random_exponential(multiplier=1, max=20),  # Delay = multiplier * 2^attempt +/- jitter
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(Exception),
)
async def _generate_with_retry(job: CopyJob, semaphore: asyncio.Semaphore) -> GeneratedCopy:
    """Single job execution, gated by the semaphore and protected by retries."""
    prompt = compile_prompt(
        product_name=job.product_name,
        platform=job.platform,
        tone=job.tone,
        product_description=job.product_description,
    )
    async with semaphore:  # blocks here if MAX_CONCURRENT_REQUESTS is already in flight
        return await generate_copy_async(prompt, temperature=job.temperature, top_p=job.top_p)


async def run_batch(jobs: List[CopyJob]) -> List[GeneratedCopy]:
    """
    Run many CopyJobs concurrently (one waiter, many kitchen tickets —
    slide 8's restaurant analogy). Uses asyncio.gather so results come
    back in the same order as the input jobs.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    tasks = [_generate_with_retry(job, semaphore) for job in jobs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: List[GeneratedCopy] = []
    for job, result in zip(jobs, results):
        if isinstance(result, Exception):
            print(f"[FAILED] {job.product_name}/{job.platform}/{job.tone}: {result}")
        else:
            output.append(result)
    return output
