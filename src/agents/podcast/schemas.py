"""Structured contracts for the podcast pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SegmentPlan(BaseModel):
    index: int = Field(ge=0)
    title: str
    goal: str


class EpisodePlan(BaseModel):
    title: str
    hook: str
    segments: list[SegmentPlan] = Field(min_length=2, max_length=8)


class EpisodeCritique(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)