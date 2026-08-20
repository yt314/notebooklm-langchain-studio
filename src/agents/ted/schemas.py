"""Structured-output contracts between the TED talk pipeline's stages."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TalkBrief(BaseModel):
    topic: str = Field(description="What the talk is about, one focused sentence, in Hebrew")
    hook: str = Field(
        description="The opening idea that grabs the audience in the first 30 seconds, in Hebrew"
    )
    key_points: list[str] = Field(
        description="Exactly 3 key points the talk develops, in order, each in Hebrew"
    )


class CritiqueResult(BaseModel):
    passed: bool = Field(description="True if the script is ready to be shown to the user")
    issues: list[str] = Field(description="Concrete problems to fix; empty when passed")
