"""
models.py
---------
Strict output schemas (Pydantic) for the Automated Copywriting & Tone
Transformer. Every piece of generated copy is validated against these
models before it is considered "done" — this is the project's
"Pydantic Validation" gate from the architecture diagram.
"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator

# Platform-specific hard constraints (used both for prompt injection
# AND for post-generation compliance checking).
PLATFORM_RULES = {
    "linkedin": {"max_chars": 3000, "style": "professional, value-driven, thought-leadership"},
    "instagram": {"max_chars": 2200, "style": "punchy, visual, hashtag-friendly"},
    "email": {"max_chars": 1500, "style": "structured with a clear subject line and CTA"},
    "twitter": {"max_chars": 280, "style": "extremely concise, single hook"},
}


class GeneratedCopy(BaseModel):
    """Structured response the model MUST return."""

    headline: str = Field(..., description="A short, attention-grabbing headline.")
    body: str = Field(..., description="The main marketing copy.")
    call_to_action: str = Field(..., description="A short closing CTA line.")
    platform: str
    tone: str
    word_count: int = Field(..., description="Total word count of headline+body+CTA combined.")
    compliance_check: bool = Field(
        default=True, description="True if body length is within the platform's hard limit."
    )

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        v_lower = v.lower()
        if v_lower not in PLATFORM_RULES:
            raise ValueError(f"Unsupported platform '{v}'. Choose from {list(PLATFORM_RULES)}")
        return v_lower

    def check_compliance(self) -> bool:
        """Re-validate the hard character limit independent of the model's self-report."""
        limit = PLATFORM_RULES[self.platform]["max_chars"]
        total_len = len(self.headline) + len(self.body) + len(self.call_to_action)
        self.compliance_check = total_len <= limit
        return self.compliance_check
