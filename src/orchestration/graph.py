"""LangGraph orchestration for the multiagent pipeline.

Two graphs are built separately:

* ``build_planner_graph`` — a single-node graph that runs the Planner. If the
  Planner produced clarification questions the caller should stop there and
  persist the state; otherwise the caller continues with the pipeline graph.
* ``build_pipeline_graph`` — requirements → designer → validator, with a
  conditional edge that may loop back to requirements or designer (max 2
  revisions) or terminate.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agents.architecture_designer import ArchitectureDesignerAgent
from src.agents.planner import PlannerAgent
from src.agents.requirements_tech_stack import RequirementsTechStackAgent
from src.agents.validator_aggregator import ValidatorAggregatorAgent
from src.orchestration.state import PipelineState


def build_planner_graph(provider: str | None = None, model: str | None = None):
    """Compile a single-node graph that runs only the Planner."""
    agent = PlannerAgent(provider=provider, model=model)

    graph = StateGraph(PipelineState)
    graph.add_node("planner_node", agent.run)
    graph.add_edge(START, "planner_node")
    graph.add_edge("planner_node", END)

    return graph.compile()


def route_after_validation(state: PipelineState) -> str:
    """Conditional edge: decide whether to loop back or terminate.

    - If the Validator produced a non-empty markdown_content, terminate.
    - Otherwise, route based on revision_target.
    - Safety fallback: terminate if target is unknown.
    """
    if state.get("markdown_content"):
        return END

    target = state.get("revision_target", "") or ""
    if target == "requirements":
        return "requirements_node"
    if target == "designer":
        return "designer_node"
    return END


def build_pipeline_graph(
    requirements_provider: str | None = None,
    requirements_model: str | None = None,
    designer_provider: str | None = None,
    designer_model: str | None = None,
    validator_provider: str | None = None,
    validator_model: str | None = None,
):
    """Compile the requirements → designer → validator graph with a feedback loop."""
    requirements_agent = RequirementsTechStackAgent(
        provider=requirements_provider, model=requirements_model
    )
    designer_agent = ArchitectureDesignerAgent(
        provider=designer_provider, model=designer_model
    )
    validator_agent = ValidatorAggregatorAgent(
        provider=validator_provider, model=validator_model
    )

    graph = StateGraph(PipelineState)
    graph.add_node("requirements_node", requirements_agent.run)
    graph.add_node("designer_node", designer_agent.run)
    graph.add_node("validator_node", validator_agent.run)

    graph.add_edge(START, "requirements_node")
    graph.add_edge("requirements_node", "designer_node")
    graph.add_edge("designer_node", "validator_node")
    graph.add_conditional_edges(
        "validator_node",
        route_after_validation,
        {
            "requirements_node": "requirements_node",
            "designer_node": "designer_node",
            END: END,
        },
    )

    return graph.compile()
