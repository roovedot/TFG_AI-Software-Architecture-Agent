"""Tests for the single-agent baseline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.single_agent import SingleAgent
from src.models.output import (
    AnalysisReport,
    ArchitectureProposal,
    Requirement,
    RiskAssessment,
    TechRecommendation,
)


@pytest.fixture
def sample_report():
    """A minimal valid AnalysisReport for testing."""
    return AnalysisReport(
        requirements=[
            Requirement(
                description="User authentication",
                type="functional",
                priority="must_have",
            ),
        ],
        tech_stack=[
            TechRecommendation(
                category="backend_framework",
                name="FastAPI",
                justification="Async support, good performance",
                pros=["Fast", "Modern"],
                cons=["Smaller ecosystem"],
                alternatives=["Django", "Flask"],
            ),
        ],
        architecture=ArchitectureProposal(
            pattern="monolith",
            justification="Small team, simple project",
            components=[{"name": "API", "responsibility": "Handle requests"}],
            design_patterns=["Repository"],
            infrastructure={"hosting": "AWS"},
        ),
        risks=[
            RiskAssessment(
                risk="Scope creep",
                severity="medium",
                mitigation="Agile sprints",
            ),
        ],
        development_plan=[
            {"phase": "MVP", "duration": "2 months", "deliverables": ["Core API"]},
        ],
        summary="A simple monolithic application.",
    )


@pytest.fixture
def mock_ai_message(sample_report):
    """Mock AIMessage with usage metadata."""
    msg = MagicMock()
    msg.content = sample_report.model_dump_json()
    msg.usage_metadata = {
        "input_tokens": 1500,
        "output_tokens": 800,
    }
    return msg


@pytest.fixture
def mock_llm(sample_report, mock_ai_message):
    """Mock LLM that returns a structured output result."""
    llm = AsyncMock()
    structured = AsyncMock()
    structured.ainvoke.return_value = {
        "raw": mock_ai_message,
        "parsed": sample_report,
        "parsing_error": None,
    }
    llm.with_structured_output.return_value = structured
    return llm


@pytest.mark.asyncio
async def test_single_agent_returns_report_and_metrics(mock_llm, sample_report):
    """The agent should return a valid final_report and metrics in state."""
    agent = SingleAgent(llm=mock_llm)

    with patch("src.agents.single_agent.settings") as mock_settings:
        mock_settings.llm_provider.value = "openai"
        mock_settings.llm_provider = MagicMock()
        mock_settings.llm_provider.__eq__ = lambda self, other: False
        mock_settings.llm_provider.value = "openai"
        mock_settings.openai_model = "gpt-4o"

        state = {"project_description": "An e-commerce platform", "user_documents": []}
        result = await agent.run(state)

    assert "final_report" in result
    assert "metrics" in result

    report = AnalysisReport.model_validate(result["final_report"])
    assert len(report.requirements) == 1
    assert report.requirements[0].description == "User authentication"

    metrics = result["metrics"]
    assert metrics["input_tokens"] == 1500
    assert metrics["output_tokens"] == 800
    assert metrics["total_tokens"] == 2300
    assert metrics["execution_time_seconds"] > 0


@pytest.mark.asyncio
async def test_single_agent_extracts_tokens_from_usage_metadata():
    """Token extraction should work with usage_metadata."""
    agent = SingleAgent(llm=AsyncMock())
    msg = MagicMock()
    msg.usage_metadata = {"input_tokens": 100, "output_tokens": 50}

    inp, out = agent._extract_tokens(msg)
    assert inp == 100
    assert out == 50


@pytest.mark.asyncio
async def test_single_agent_extracts_tokens_from_ollama_metadata():
    """Token extraction should work with Ollama response_metadata."""
    agent = SingleAgent(llm=AsyncMock())
    msg = MagicMock()
    msg.usage_metadata = None
    msg.response_metadata = {"prompt_eval_count": 200, "eval_count": 100}

    inp, out = agent._extract_tokens(msg)
    assert inp == 200
    assert out == 100


@pytest.mark.asyncio
async def test_single_agent_handles_missing_token_data():
    """Token extraction should return (0, 0) when no metadata is available."""
    agent = SingleAgent(llm=AsyncMock())
    msg = MagicMock()
    msg.usage_metadata = None
    msg.response_metadata = {}

    inp, out = agent._extract_tokens(msg)
    assert inp == 0
    assert out == 0
