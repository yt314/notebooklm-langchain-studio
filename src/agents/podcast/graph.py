"""Podcast script graph with parallel research and whole-episode review."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.podcast.nodes import (
    after_approval,
    after_critique,
    approval,
    assemble_episode,
    critique_episode,
    fan_out_segments,
    plan_episode,
    research_segment,
    revise_episode,
    write_segment,
)
from agents.podcast.state import PodcastState


def build_podcast_graph(checkpointer=None):
    builder = StateGraph(PodcastState)
    builder.add_node("plan_episode", plan_episode)
    builder.add_node("research_segment", research_segment)
    builder.add_node("write_segment", write_segment)
    builder.add_node("assemble_episode", assemble_episode)
    builder.add_node("critique_episode", critique_episode)
    builder.add_node("revise_episode", revise_episode)
    builder.add_node("approval", approval)

    builder.add_edge(START, "plan_episode")
    builder.add_conditional_edges("plan_episode", fan_out_segments)
    builder.add_edge("research_segment", "write_segment")
    builder.add_edge("write_segment", "assemble_episode")
    builder.add_edge("assemble_episode", "critique_episode")
    builder.add_conditional_edges(
        "critique_episode", after_critique, {"revise": "revise_episode", "approval": "approval"}
    )
    builder.add_edge("revise_episode", "critique_episode")
    builder.add_conditional_edges("approval", after_approval, {"revise": "revise_episode", "done": END})
    return builder.compile(checkpointer=checkpointer)