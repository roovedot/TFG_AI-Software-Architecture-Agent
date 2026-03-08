"""Tests for the baseline analysis endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from src.models.output import (
    AnalysisReport,
    ArchitectureProposal,
    Requirement,
    RiskAssessment,
    TechRecommendation,
)


def _make_mock_graph_result():
    """Create a mock graph result matching what the single agent returns."""
    report = AnalysisReport(
        requirements=[
            Requirement(description="Auth system", type="functional", priority="must_have"),
        ],
        tech_stack=[
            TechRecommendation(
                category="backend",
                name="FastAPI",
                justification="Fast and modern",
                pros=["Async"],
                cons=["Young"],
                alternatives=["Django"],
            ),
        ],
        architecture=ArchitectureProposal(
            pattern="monolith",
            justification="Small project",
            components=[],
            design_patterns=["MVC"],
            infrastructure={"hosting": "AWS"},
        ),
        risks=[
            RiskAssessment(risk="Delays", severity="low", mitigation="Buffer time"),
        ],
        development_plan=[{"phase": "MVP", "duration": "1 month"}],
        summary="Simple system.",
    )
    return {
        "final_report": report.model_dump(),
        "metrics": {
            "provider": "openai",
            "model": "gpt-4o",
            "input_tokens": 1000,
            "output_tokens": 500,
            "total_tokens": 1500,
            "execution_time_seconds": 3.5,
            "estimated_cost_usd": 0.0075,
        },
    }


def test_baseline_endpoint_success(client):
    """POST /analyze/baseline should return a valid BaselineResult."""
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = _make_mock_graph_result()

    with patch(
        "src.api.routes.build_single_agent_graph", return_value=mock_graph
    ):
        response = client.post(
            "/analyze/baseline",
            json={
                "description": "An e-commerce platform for selling books online.",
                "documents": [],
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "report" in data
    assert "metrics" in data
    assert data["metrics"]["provider"] == "openai"
    assert len(data["report"]["requirements"]) == 1


def test_baseline_endpoint_validation_error(client):
    """POST /analyze/baseline with too short description should return 422."""
    response = client.post(
        "/analyze/baseline",
        json={"description": "short", "documents": []},
    )
    assert response.status_code == 422


def test_baseline_endpoint_llm_failure(client):
    """POST /analyze/baseline should return 500 when the LLM call fails."""
    mock_graph = AsyncMock()
    mock_graph.ainvoke.side_effect = RuntimeError("LLM connection failed")

    with patch(
        "src.api.routes.build_single_agent_graph", return_value=mock_graph
    ):
        response = client.post(
            "/analyze/baseline",
            json={
                "description": "A project management tool for remote teams with 50 users.",
                "documents": [],
            },
        )

    assert response.status_code == 500
    assert "Analysis failed" in response.json()["detail"]
