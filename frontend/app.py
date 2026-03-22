"""Streamlit frontend for the TFG Architecture Agent."""

from __future__ import annotations

import os
import time

import httpx
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

SUPPORTED_FILE_TYPES = [
    "txt", "md", "csv", "json", "xml", "yaml", "yml",
    "py", "js", "ts", "java", "go", "rs", "html", "css",
    "toml", "ini", "sh", "sql",
    "pdf",
    "png", "jpg", "jpeg", "gif", "webp",
    "htm",
]

RATING_CRITERIA = [
    ("identifies_right_concerns", "Identifica las preocupaciones correctas"),
    ("adherence_to_request", "Se ajusta a lo pedido"),
    ("completeness_of_analysis", "Completitud del analisis tecnico"),
    ("tech_stack_quality", "Calidad de la recomendacion tecnologica"),
    ("document_clarity", "Claridad y estructura del documento"),
    ("risk_identification", "Identificacion de riesgos"),
    ("actionability", "Plan de desarrollo accionable"),
]

st.set_page_config(
    page_title="Architecture Agent",
    layout="wide",
)

# ── Session state initialization ─────────────────────────────────────────────

if "view" not in st.session_state:
    st.session_state["view"] = "analyze"
if "selected_project_id" not in st.session_state:
    st.session_state["selected_project_id"] = None
if "last_result" not in st.session_state:
    st.session_state["last_result"] = None

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

    # ── Project History ──────────────────────────────────────────────────────

    st.divider()
    st.header("Historial de Proyectos")

    if st.button("Nuevo analisis", use_container_width=True):
        st.session_state["view"] = "analyze"
        st.session_state["selected_project_id"] = None
        st.session_state["last_result"] = None
        st.rerun()

    projects_list = []
    if health:
        try:
            projects_list = httpx.get(f"{API_BASE_URL}/projects", timeout=5).json()
        except httpx.ConnectError:
            pass

    for p in projects_list:
        pid = p["id"]
        date_str = p["created_at"][:10] if p["created_at"] else ""
        rating_icon = " *" if p["has_rating"] else ""

        col_btn, col_del = st.columns([5, 1])
        with col_btn:
            label = f"{p['description_preview'][:50]}\n{p['model']} | {date_str}{rating_icon}"
            if st.button(label, key=f"proj_{pid}", use_container_width=True):
                st.session_state["view"] = "detail"
                st.session_state["selected_project_id"] = pid
                st.session_state["last_result"] = None
                st.rerun()
        with col_del:
            if st.button("x", key=f"del_{pid}"):
                try:
                    httpx.delete(f"{API_BASE_URL}/projects/{pid}", timeout=10)
                except httpx.ConnectError:
                    st.error("Cannot connect to API")
                st.rerun()


# ── Helper: render results ───────────────────────────────────────────────────


def render_metrics(metrics: dict) -> None:
    """Render the metrics bar."""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Time", f"{metrics['execution_time_seconds']:.1f}s")
    col2.metric("Input tokens", f"{metrics['input_tokens']:,}")
    col3.metric("Output tokens", f"{metrics['output_tokens']:,}")
    col4.metric("Est. cost", f"${metrics['estimated_cost_usd']:.4f}")


def render_report(markdown_content: str) -> None:
    """Render the download button and markdown report."""
    st.download_button(
        label="Descargar .md",
        data=markdown_content,
        file_name="architecture_report.md",
        mime="text/markdown",
    )
    st.divider()
    st.markdown(markdown_content)


def render_rating_form(project_id: str, existing_ratings: dict | None) -> None:
    """Render the rating form for a project."""
    st.divider()
    st.subheader("Evaluar resultado")

    ratings = {}
    for key, label in RATING_CRITERIA:
        default = existing_ratings.get(key, 5) if existing_ratings else 5
        ratings[key] = st.slider(label, 0, 10, default, key=f"rating_{key}_{project_id}")

    default_comments = existing_ratings.get("comments", "") if existing_ratings else ""
    comments = st.text_area(
        "Comentarios adicionales", value=default_comments, key=f"comments_{project_id}"
    )

    if st.button("Guardar evaluacion", type="primary", key=f"save_rating_{project_id}"):
        ratings["comments"] = comments
        try:
            resp = httpx.put(
                f"{API_BASE_URL}/projects/{project_id}/ratings",
                json=ratings,
                timeout=10,
            )
            resp.raise_for_status()
            st.success("Evaluacion guardada")
            st.rerun()
        except httpx.HTTPStatusError as e:
            st.error(f"Error al guardar: {e.response.text}")
        except httpx.ConnectError:
            st.error("Cannot connect to API")


# ── Main area ────────────────────────────────────────────────────────────────

if st.session_state["view"] == "detail":
    # ── Detail view: show a saved project ────────────────────────────────
    project_id = st.session_state["selected_project_id"]
    if not project_id:
        st.warning("No project selected")
        st.stop()

    try:
        resp = httpx.get(f"{API_BASE_URL}/projects/{project_id}", timeout=10)
        resp.raise_for_status()
        project = resp.json()
    except httpx.HTTPStatusError:
        st.error("Project not found")
        st.stop()
    except httpx.ConnectError:
        st.error(f"Cannot connect to API at {API_BASE_URL}")
        st.stop()

    st.title("Architecture Agent — Baseline")
    st.caption("Single-agent baseline for automated software architecture design")

    # Project info
    st.subheader("Descripcion del proyecto")
    st.text(project["description"])

    # Files
    if project.get("files"):
        st.subheader("Archivos adjuntos")
        for f in project["files"]:
            size_kb = f["size"] / 1024
            st.markdown(
                f"- **{f['name']}** ({size_kb:.1f} KB) — "
                f"[Descargar]({API_BASE_URL}/projects/{project_id}/files/{f['file_id']})"
            )

    # Metrics & report
    st.divider()
    render_metrics(project["metrics"])
    render_report(project["markdown_content"])

    # Rating form
    render_rating_form(project_id, project.get("ratings"))

else:
    # ── Analyze view: new analysis ───────────────────────────────────────
    st.title("Architecture Agent — Baseline")
    st.caption("Single-agent baseline for automated software architecture design")

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

    # ── Run analysis ─────────────────────────────────────────────────────

    if analyze and project_description and selected_provider and selected_model:
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
                st.session_state["last_result"] = data
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

    # ── Results (persisted in session_state) ──────────────────────────────

    if st.session_state.get("last_result"):
        data = st.session_state["last_result"]
        markdown_content = data["markdown_content"]
        metrics = data["metrics"]
        project_id = data.get("project_id")

        st.divider()
        render_metrics(metrics)
        render_report(markdown_content)

        # Rating form (if project was saved)
        if project_id:
            render_rating_form(project_id, None)
