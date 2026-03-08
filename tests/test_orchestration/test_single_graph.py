"""Tests for the single-agent LangGraph graph."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.orchestration.single_graph import build_single_agent_graph


def test_graph_compiles():
    """The single-agent graph should compile without errors."""
    with patch("src.orchestration.single_graph.SingleAgent"):
        graph = build_single_agent_graph()
        assert graph is not None


@pytest.mark.asyncio
async def test_graph_executes_single_agent():
    """The graph should pass state through the single agent node."""
    expected_result = {
        "final_report": {"summary": "test"},
        "metrics": {"provider": "openai"},
    }

    mock_agent = AsyncMock()
    mock_agent.run.return_value = expected_result

    with patch("src.orchestration.single_graph.SingleAgent", return_value=mock_agent):
        graph = build_single_agent_graph()
        result = await graph.ainvoke({
            "project_description": "A test project",
            "user_documents": [],
        })

    assert result["final_report"] == {"summary": "test"}
    assert result["metrics"] == {"provider": "openai"}
    mock_agent.run.assert_called_once()
