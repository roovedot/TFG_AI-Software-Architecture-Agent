"""LangGraph graph for the single-agent baseline pipeline."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agents.single_agent import SingleAgent
from src.orchestration.state import PipelineState


def build_single_agent_graph() -> StateGraph:
    """Build and compile a single-node LangGraph for the baseline.

    Even with one node, using LangGraph provides:
    - Consistent execution interface with the future multi-agent graph.
    - Automatic LangSmith tracing of the graph structure.
    - Clean state management via PipelineState.
    """
    agent = SingleAgent()

    graph = StateGraph(PipelineState)
    graph.add_node("single_agent", agent.run)
    graph.add_edge(START, "single_agent")
    graph.add_edge("single_agent", END)

    return graph.compile()
