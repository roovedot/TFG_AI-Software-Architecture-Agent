"""Streamlit frontend for the TFG Architecture Agent."""

from __future__ import annotations

import os

import httpx
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

SUPPORTED_FILE_TYPES = [
    "txt", "md", "csv", "json", "xml", "yaml", "yml",
    "py", "js", "ts", "java", "go", "rs", "html", "css",
    "toml", "ini", "sh", "sql",
    "pdf",
    "png", "jpg", "jpeg", "gif", "webp",
]

st.set_page_config(
    page_title="Architecture Agent",
    layout="wide",
)

st.title("Architecture Agent — Baseline")
st.caption("Single-agent baseline for automated software architecture design")

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Configuration")

    # Health check
    try:
        health = httpx.get(f"{API_BASE_URL}/health", timeout=5).json()
        st.success("API connected")
        st.metric("Environment", health["environment"])
    except httpx.ConnectError:
        st.error(f"Cannot connect to API at {API_BASE_URL}")
        health = None

    # Model selector
    available_models = []
    selected_provider = None
    selected_model = None
    model_supports_vision = False

    if health:
        try:
            available_models = httpx.get(f"{API_BASE_URL}/models", timeout=5).json()
        except httpx.ConnectError:
            st.warning("Could not fetch model list")

    if available_models:
        model_labels = [m["label"] for m in available_models]
        selected_idx = st.selectbox(
            "Model",
            range(len(model_labels)),
            format_func=lambda i: model_labels[i],
        )
        selected = available_models[selected_idx]
        selected_provider = selected["provider"]
        selected_model = selected["model_id"]
        model_supports_vision = selected["supports_vision"]

        tier_colors = {"economic": "blue", "performance": "green", "local": "orange"}
        tier = selected["tier"]
        st.caption(f":{tier_colors.get(tier, 'gray')}[{tier.upper()}] — {selected_provider}")
    else:
        st.warning("No models available. Check API keys in .env")

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

# File uploader (disabled for non-vision models like Ollama)
uploaded_files = []
if selected_provider == "ollama":
    st.info("La subida de archivos no esta disponible con el modelo local.")
elif selected_provider:
    uploaded_files = st.file_uploader(
        "Adjuntar archivos (arrastra o haz click)",
        accept_multiple_files=True,
        type=SUPPORTED_FILE_TYPES,
        help="Texto, PDFs e imagenes. Los archivos se envian al modelo como contexto adicional.",
    ) or []

analyze_disabled = not project_description or health is None or not selected_model
analyze = st.button(
    "Analyze", type="primary", disabled=analyze_disabled, use_container_width=True
)

# ── Analysis ─────────────────────────────────────────────────────────────────

if analyze and project_description and selected_provider and selected_model:
    # Build multipart form data
    form_data = {
        "description": project_description,
        "provider": selected_provider,
        "model": selected_model,
    }

    files_to_upload = []
    for f in uploaded_files:
        files_to_upload.append(("files", (f.name, f.read(), f.type)))

    with st.spinner("Analyzing project... This may take a minute."):
        try:
            response = httpx.post(
                f"{API_BASE_URL}/analyze/baseline",
                data=form_data,
                files=files_to_upload if files_to_upload else None,
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
