"""Assembles the TED talk LangGraph graph. Grows as pipeline steps are added."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.ted.nodes import (
    after_approval,
    after_critique,
    approval,
    count_words,
    critique_script,
    gather_context,
    plan_talk,
    revise,
    write_talk,
)
from agents.ted.state import TedState


def build_ted_graph(checkpointer=None):
    builder = StateGraph(TedState)
    builder.add_node("plan_talk", plan_talk)
    builder.add_node("gather_context", gather_context)
    builder.add_node("write_talk", write_talk)
    builder.add_node("count_words", count_words)
    builder.add_node("critique_script", critique_script)
    builder.add_node("revise", revise)
    builder.add_node("approval", approval)

    builder.add_edge(START, "plan_talk")
    builder.add_edge("plan_talk", "gather_context")
    builder.add_edge("gather_context", "write_talk")
    builder.add_edge("write_talk", "count_words")
    builder.add_edge("count_words", "critique_script")
    builder.add_conditional_edges(
        "critique_script", after_critique, {"approval": "approval", "revise": "revise"}
    )
    builder.add_conditional_edges("approval", after_approval, {"revise": "revise", "done": END})
    builder.add_edge("revise", "count_words")

    return builder.compile(checkpointer=checkpointer)
