"""Streamlit frontend for the TFG Architecture Agent."""

from __future__ import annotations

import os

import httpx
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Architecture Agent",
    layout="wide",
)

st.title("Architecture Agent — Baseline")
st.caption("Single-agent baseline for automated software architecture design")

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Configuration")
    try:
        health = httpx.get(f"{API_BASE_URL}/health", timeout=5).json()
        st.success("API connected")
        st.metric("Environment", health["environment"])
        st.metric("LLM Provider", health["llm_provider"])
    except httpx.ConnectError:
        st.error(f"Cannot connect to API at {API_BASE_URL}")
        health = None

# ── Input ────────────────────────────────────────────────────────────────────

project_description = st.text_area(
    "Project Description",
    height=250,
    placeholder=(
        "Describe your software project here. Include information about: "
        "what the system does, expected users, scale, team size, timeline, "
        "constraints, and any specific technology preferences..."
    ),
)

with st.expander("Additional documents (optional)"):
    extra_docs = st.text_area(
        "Paste additional requirements, specs, or context here",
        height=150,
        label_visibility="collapsed",
    )

analyze_disabled = not project_description or health is None
analyze = st.button(
    "Analyze", type="primary", disabled=analyze_disabled, use_container_width=True
)

# ── Analysis ─────────────────────────────────────────────────────────────────

if analyze and project_description:
    documents = [extra_docs] if extra_docs else []
    payload = {"description": project_description, "documents": documents}

    with st.spinner("Analyzing project... This may take a minute."):
        try:
            response = httpx.post(
                f"{API_BASE_URL}/analyze/baseline",
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            st.error(
                "Analysis timed out. Try a shorter description or check LLM availability."
            )
            st.stop()
        except httpx.HTTPStatusError as e:
            st.error(f"API error: {e.response.text}")
            st.stop()
        except httpx.ConnectError:
            st.error(f"Cannot connect to API at {API_BASE_URL}")
            st.stop()

    markdown_content = data["markdown_content"]
    metrics = data["metrics"]

    # ── Metrics bar ──────────────────────────────────────────────────────

    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Time", f"{metrics['execution_time_seconds']:.1f}s")
    col2.metric("Input tokens", f"{metrics['input_tokens']:,}")
    col3.metric("Output tokens", f"{metrics['output_tokens']:,}")
    col4.metric("Est. cost", f"${metrics['estimated_cost_usd']:.4f}")

    # ── Download button ───────────────────────────────────────────────────

    st.download_button(
        label="Descargar .md",
        data=markdown_content,
        file_name="architecture_report.md",
        mime="text/markdown",
    )

    st.divider()

    # ── Markdown report ───────────────────────────────────────────────────

    st.markdown(markdown_content)
