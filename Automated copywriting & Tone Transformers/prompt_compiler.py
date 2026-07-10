"""
prompt_compiler.py
-------------------
"Protecting Brand Voice with the Master Instruction Template" (slide 6).

The end user only supplies raw facts (product name, platform, tone,
description). This module is the *gatekeeper*: it owns the hidden
master template and injects user variables into it via f-strings,
appending strict platform-specific constraints before the payload
is ever sent to the model. The raw user input never reaches the API
unstructured.
"""

from __future__ import annotations
from models import PLATFORM_RULES


# The "hidden" master template (slide 6 — "Dynamic Compilation").
# Users never see or edit this directly; they only provide variables.
_MASTER_TEMPLATE = """\
You are an expert marketing copywriter at a brand-safety-conscious agency.

TASK:
Write marketing copy for the product "{product_name}" intended for the
platform "{platform}". The required tone is "{tone}".

PRODUCT DESCRIPTION (raw facts provided by the client — do not invent
features that aren't implied by this description):
\"\"\"{product_description}\"\"\"

PLATFORM CONSTRAINTS (must be respected exactly):
- Hard character limit (headline+body+CTA combined): {max_chars} characters.
- Stylistic expectation for this platform: {platform_style}.

OUTPUT FORMAT:
Return ONLY a JSON object with these exact keys, no markdown fences, no preamble:
{{
  "headline": "...",
  "body": "...",
  "call_to_action": "...",
  "platform": "{platform}",
  "tone": "{tone}",
  "word_count": <integer>,
  "compliance_check": <true/false, whether you respected the character limit>
}}
"""


def compile_prompt(product_name: str, platform: str, tone: str, product_description: str) -> str:
    """
    Dynamically compile the master instruction template with user-defined
    variables. Raises ValueError for unsupported platforms early, before
    any API call is made.
    """
    platform_key = platform.lower()
    if platform_key not in PLATFORM_RULES:
        raise ValueError(
            f"Unsupported platform '{platform}'. Choose from {list(PLATFORM_RULES)}"
        )

    rules = PLATFORM_RULES[platform_key]

    return _MASTER_TEMPLATE.format(
        product_name=product_name,
        platform=platform_key,
        tone=tone,
        product_description=product_description.strip(),
        max_chars=rules["max_chars"],
        platform_style=rules["style"],
    )
