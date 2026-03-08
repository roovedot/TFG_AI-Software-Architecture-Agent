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

    report = data["report"]
    metrics = data["metrics"]

    # ── Metrics bar ──────────────────────────────────────────────────────

    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Time", f"{metrics['execution_time_seconds']:.1f}s")
    col2.metric("Input tokens", f"{metrics['input_tokens']:,}")
    col3.metric("Output tokens", f"{metrics['output_tokens']:,}")
    col4.metric("Est. cost", f"${metrics['estimated_cost_usd']:.4f}")

    # ── Results tabs ─────────────────────────────────────────────────────

    tabs = st.tabs([
        "Summary",
        "Requirements",
        "Tech Stack",
        "Architecture",
        "Risks",
        "Dev Plan",
        "Raw JSON",
    ])

    # Summary
    with tabs[0]:
        st.markdown(report.get("summary", "*No summary generated.*"))

    # Requirements
    with tabs[1]:
        reqs = report.get("requirements", [])
        if reqs:
            st.dataframe(
                reqs,
                column_config={
                    "description": st.column_config.TextColumn(
                        "Description", width="large"
                    ),
                    "type": st.column_config.TextColumn("Type", width="small"),
                    "priority": st.column_config.TextColumn("Priority", width="small"),
                },
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No requirements extracted.")

    # Tech Stack
    with tabs[2]:
        for tech in report.get("tech_stack", []):
            with st.expander(f"**{tech['name']}** — {tech['category']}"):
                st.write(tech.get("justification", ""))
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Pros**")
                    for pro in tech.get("pros", []):
                        st.markdown(f"- {pro}")
                with c2:
                    st.markdown("**Cons**")
                    for con in tech.get("cons", []):
                        st.markdown(f"- {con}")
                alts = tech.get("alternatives", [])
                if alts:
                    st.caption(f"Alternatives: {', '.join(alts)}")

    # Architecture
    with tabs[3]:
        arch = report.get("architecture")
        if arch:
            st.subheader(f"Pattern: {arch['pattern']}")
            st.write(arch.get("justification", ""))

            if arch.get("components"):
                st.markdown("### Components")
                for comp in arch["components"]:
                    name = comp.get("name", "Unknown")
                    resp = comp.get("responsibility", "")
                    tech_name = comp.get("technology", "")
                    st.markdown(f"- **{name}** ({tech_name}): {resp}")

            if arch.get("design_patterns"):
                st.markdown("### Design Patterns")
                st.write(", ".join(arch["design_patterns"]))

            if arch.get("infrastructure"):
                st.markdown("### Infrastructure")
                for key, value in arch["infrastructure"].items():
                    st.markdown(f"- **{key}**: {value}")
        else:
            st.info("No architecture proposal generated.")

    # Risks
    with tabs[4]:
        for risk in report.get("risks", []):
            severity = risk.get("severity", "medium")
            if severity == "high":
                st.error(f"**{risk['risk']}**\n\nMitigation: {risk['mitigation']}")
            elif severity == "medium":
                st.warning(f"**{risk['risk']}**\n\nMitigation: {risk['mitigation']}")
            else:
                st.info(f"**{risk['risk']}**\n\nMitigation: {risk['mitigation']}")

    # Development Plan
    with tabs[5]:
        for phase in report.get("development_plan", []):
            with st.expander(
                f"**{phase.get('phase', 'Phase')}** — {phase.get('duration', 'TBD')}"
            ):
                deliverables = phase.get("deliverables", [])
                for d in deliverables:
                    st.markdown(f"- {d}")
                deps = phase.get("dependencies", [])
                if deps:
                    st.caption(f"Depends on: {', '.join(deps)}")

    # Raw JSON
    with tabs[6]:
        st.json(data)
