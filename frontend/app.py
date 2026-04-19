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

PROGRESS_MESSAGES = [
    "Procesando archivos adjuntos...",
    "Construyendo el prompt para el modelo...",
    "Enviando peticion al LLM...",
    "El modelo esta analizando tu proyecto...",
    "Generando recomendaciones de arquitectura...",
    "Evaluando stack tecnologico...",
    "Identificando riesgos y mitigaciones...",
    "Redactando el informe final...",
    "Casi listo, finalizando el documento...",
]

MULTIAGENT_STEP_LABELS = {
    "planner": "Paso 1/4: Planificando el analisis...",
    "waiting_clarification": "Esperando respuestas de clarificacion del usuario...",
    "requirements": "Paso 2/4: Extrayendo requisitos y seleccionando stack...",
    "designer": "Paso 3/4: Disenando la arquitectura...",
    "validator": "Paso 4/4: Validando y consolidando el informe...",
    "revision_1": "Revision 1/2: Mejorando el resultado...",
    "revision_2": "Revision 2/2: Ultima pasada de mejora...",
    "completed": "Analisis completado",
}

MULTIAGENT_AGENT_NAMES = ["planner", "requirements", "designer", "validator"]
MULTIAGENT_AGENT_LABELS = {
    "planner": "Planner",
    "requirements": "Requirements & Tech-Stack",
    "designer": "Architecture Designer",
    "validator": "Validator & Aggregator",
}

st.set_page_config(
    page_title="Architecture Agent",
    layout="wide",
)

# ── Session state initialization ─────────────────────────────────────────────

if "view" not in st.session_state:
    st.session_state["view"] = "analyze"
if "selected_project_id" not in st.session_state:
    st.session_state["selected_project_id"] = None
if "processing_start_time" not in st.session_state:
    st.session_state["processing_start_time"] = None
if "mode" not in st.session_state:
    st.session_state["mode"] = "mono"  # "mono" | "multi"
if "multi_same_model" not in st.session_state:
    st.session_state["multi_same_model"] = True


# ── Helpers ──────────────────────────────────────────────────────────────────


def _find_model_index(available: list[dict], provider: str | None, model_id: str | None) -> int:
    if not provider or not model_id:
        return 0
    for i, m in enumerate(available):
        if m["provider"] == provider and m["model_id"] == model_id:
            return i
    return 0


def _model_selectbox(
    label: str, available: list[dict], key: str
) -> tuple[str | None, str | None, bool]:
    """Render a model selectbox, returning (provider, model_id, supports_vision)."""
    labels = [m["label"] for m in available]
    idx = st.selectbox(
        label, range(len(labels)), format_func=lambda i: labels[i], key=key
    )
    sel = available[idx]
    return sel["provider"], sel["model_id"], sel["supports_vision"]


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

    available_models: list[dict] = []
    if health:
        try:
            available_models = httpx.get(f"{API_BASE_URL}/models", timeout=5).json()
        except httpx.ConnectError:
            st.warning("Could not fetch model list")

    # ── Model selection (depends on mode) ────────────────────────────────────
    mono_provider = None
    mono_model = None
    mono_supports_vision = False
    multi_configs: dict[str, dict[str, str]] = {}
    multi_any_vision = True  # conservative

    if available_models:
        mode = st.session_state["mode"]

        if mode == "mono":
            st.subheader("Modelo (monoagente)")
            mono_provider, mono_model, mono_supports_vision = _model_selectbox(
                "Model", available_models, key="mono_model_select"
            )
        else:
            st.subheader("Modelos (multiagente)")
            st.session_state["multi_same_model"] = st.toggle(
                "Usar el mismo modelo para todos los agentes",
                value=st.session_state["multi_same_model"],
                key="multi_same_toggle",
            )

            if st.session_state["multi_same_model"]:
                p, m, sv = _model_selectbox(
                    "Modelo para todos", available_models, key="multi_same_select"
                )
                for name in MULTIAGENT_AGENT_NAMES:
                    multi_configs[name] = {"provider": p, "model": m}
                multi_any_vision = sv
            else:
                supports_vision_flags = []
                for name in MULTIAGENT_AGENT_NAMES:
                    p, m, sv = _model_selectbox(
                        MULTIAGENT_AGENT_LABELS[name],
                        available_models,
                        key=f"multi_{name}_select",
                    )
                    multi_configs[name] = {"provider": p, "model": m}
                    supports_vision_flags.append(sv)
                # Only the Planner actually needs vision (only it sees images).
                multi_any_vision = supports_vision_flags[0]
    else:
        st.warning("No models available. Check API keys in .env")

    # ── Project History ──────────────────────────────────────────────────────

    st.divider()
    st.header("Historial de Proyectos")

    if st.button("Nuevo analisis", use_container_width=True):
        st.session_state["view"] = "analyze"
        st.session_state["selected_project_id"] = None
        st.session_state["processing_start_time"] = None
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
        status = p.get("status", "completed")
        ptype = p.get("pipeline_type", "baseline")
        badge = "[M]" if ptype == "multiagent" else "[B]"

        if status == "processing":
            status_icon = " ..."
        elif status == "waiting_clarification":
            status_icon = " ?"
        elif status == "error":
            status_icon = " ERR"
        elif p["has_rating"]:
            status_icon = " *"
        else:
            status_icon = ""

        col_btn, col_del = st.columns([5, 1])
        with col_btn:
            label = (
                f"{badge} {p['description_preview'][:48]}\n"
                f"{p['model']} | {date_str}{status_icon}"
            )
            if st.button(label, key=f"proj_{pid}", use_container_width=True):
                st.session_state["view"] = "detail"
                st.session_state["selected_project_id"] = pid
                if status == "processing":
                    st.session_state["processing_start_time"] = (
                        st.session_state.get("processing_start_time") or time.time()
                    )
                else:
                    st.session_state["processing_start_time"] = None
                st.rerun()
        with col_del:
            if st.button("x", key=f"del_{pid}"):
                try:
                    httpx.delete(f"{API_BASE_URL}/projects/{pid}", timeout=10)
                except httpx.ConnectError:
                    st.error("Cannot connect to API")
                if st.session_state.get("selected_project_id") == pid:
                    st.session_state["view"] = "analyze"
                    st.session_state["selected_project_id"] = None
                st.rerun()


# ── Helper: render results ───────────────────────────────────────────────────


def render_metrics(metrics: dict) -> None:
    """Render the metrics bar."""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Time", f"{float(metrics.get('execution_time_seconds') or 0):.1f}s")
    col2.metric("Input tokens", f"{int(metrics.get('input_tokens') or 0):,}")
    col3.metric("Output tokens", f"{int(metrics.get('output_tokens') or 0):,}")
    col4.metric("Est. cost", f"${float(metrics.get('estimated_cost_usd') or 0):.4f}")


def render_report(markdown_content: str, project_id: str) -> None:
    """Render the download buttons (md + pdf) and markdown report."""
    col_md, col_pdf = st.columns(2)
    with col_md:
        st.download_button(
            label="Descargar .md",
            data=markdown_content,
            file_name="architecture_report.md",
            mime="text/markdown",
            key=f"dl_md_{project_id}",
        )
    with col_pdf:
        try:
            pdf_resp = httpx.get(
                f"{API_BASE_URL}/projects/{project_id}/download/pdf",
                timeout=30,
            )
            pdf_resp.raise_for_status()
            st.download_button(
                label="Descargar .pdf",
                data=pdf_resp.content,
                file_name="architecture_report.pdf",
                mime="application/pdf",
                key=f"dl_pdf_{project_id}",
            )
        except Exception:
            st.caption("Error al generar PDF")
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


def render_chat(project_id: str, project: dict) -> None:
    """Render a chat interface for asking questions about the completed report."""
    st.divider()
    st.subheader("Chat sobre el informe")

    # Inline model selector for chat
    try:
        available_models = httpx.get(f"{API_BASE_URL}/models", timeout=5).json()
    except Exception:
        available_models = []

    if not available_models:
        st.warning("No se pudieron cargar los modelos disponibles")
        return

    # Default to the same model used for analysis
    default_idx = _find_model_index(
        available_models, project.get("provider"), project.get("model")
    )
    labels = [m["label"] for m in available_models]
    chat_model_idx = st.selectbox(
        "Modelo para el chat",
        range(len(labels)),
        format_func=lambda i: labels[i],
        index=default_idx,
        key=f"chat_model_{project_id}",
    )
    chat_sel = available_models[chat_model_idx]

    # Display existing chat history
    chat_history = project.get("chat_history") or []
    for msg in chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Pregunta algo sobre el informe...", key=f"chat_input_{project_id}")
    if user_input:
        # Show user message immediately
        with st.chat_message("user"):
            st.markdown(user_input)

        # Call API
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                try:
                    resp = httpx.post(
                        f"{API_BASE_URL}/projects/{project_id}/chat",
                        json={
                            "message": user_input,
                            "provider": chat_sel["provider"],
                            "model": chat_sel["model_id"],
                        },
                        timeout=120,
                    )
                    resp.raise_for_status()
                    assistant_msg = resp.json()
                    st.markdown(assistant_msg["content"])
                except httpx.HTTPStatusError as e:
                    st.error(f"Error: {e.response.text}")
                except httpx.ConnectError:
                    st.error("No se pudo conectar con la API")
                except httpx.ReadTimeout:
                    st.error("Timeout: la respuesta del modelo tardo demasiado")

        st.rerun()


def render_processing_view_baseline(project: dict) -> None:
    """Progress UI for a baseline project in progress."""
    elapsed = 0.0
    start = st.session_state.get("processing_start_time")
    if start:
        elapsed = time.time() - start

    msg_idx = min(int(elapsed // 7), len(PROGRESS_MESSAGES) - 1)

    with st.status("Analizando proyecto...", expanded=True, state="running"):
        st.info(
            "El analisis puede tardar entre 15 segundos y 2 minutos dependiendo del modelo. "
            "Puedes navegar a otros proyectos del historial mientras tanto — "
            "el resultado aparecera automaticamente cuando termine."
        )
        st.metric("Tiempo transcurrido", f"{elapsed:.0f}s")
        st.caption(PROGRESS_MESSAGES[msg_idx])


def render_processing_view_multiagent(project: dict) -> None:
    """Progress UI for a multiagent project, driven by current_step from Mongo."""
    elapsed = 0.0
    start = st.session_state.get("processing_start_time")
    if start:
        elapsed = time.time() - start

    current_step = project.get("current_step") or "planner"
    label = MULTIAGENT_STEP_LABELS.get(current_step, f"Paso actual: {current_step}")

    with st.status("Ejecutando pipeline multiagente...", expanded=True, state="running"):
        st.info(
            "El analisis multiagente ejecuta 4 agentes en cadena. "
            "Puedes navegar a otros proyectos mientras tanto — "
            "el resultado aparecera aqui automaticamente."
        )
        st.metric("Tiempo transcurrido", f"{elapsed:.0f}s")
        st.caption(label)

    # Show outputs already produced by previous agents.
    outputs = project.get("agent_outputs") or {}
    if outputs:
        st.subheader("Outputs intermedios")
        for name in MULTIAGENT_AGENT_NAMES:
            content = outputs.get(name)
            if not content:
                continue
            with st.expander(f"Output de {MULTIAGENT_AGENT_LABELS[name]}"):
                st.code(content, language="json")


def render_clarification_form(project_id: str, project: dict) -> None:
    """Render the clarification form when the Planner asked for user input."""
    st.divider()
    st.subheader("El Planner necesita aclaraciones")
    st.caption(
        "Responde las siguientes preguntas para que los agentes downstream "
        "puedan producir un informe ajustado a tus necesidades."
    )

    questions = project.get("clarification_questions") or []
    if not questions:
        st.warning("No hay preguntas disponibles. Intenta refrescar.")
        return

    answers: dict[str, str] = {}
    for i, q in enumerate(questions):
        question_text = q.get("question", f"Pregunta {i + 1}") if isinstance(q, dict) else str(q)
        options = list((q.get("options") or []) if isinstance(q, dict) else [])
        options_with_other = options + ["Otro (escribir abajo)"]

        choice = st.radio(
            question_text,
            options_with_other,
            key=f"clar_q_{project_id}_{i}",
        )
        if choice == "Otro (escribir abajo)":
            custom = st.text_input(
                "Tu respuesta:",
                key=f"clar_q_{project_id}_{i}_other",
            )
            answers[question_text] = custom
        else:
            answers[question_text] = choice

    if st.button("Continuar analisis", type="primary", key=f"submit_clar_{project_id}"):
        # Validate no empty answers.
        if any(not a.strip() for a in answers.values()):
            st.error("Por favor responde todas las preguntas antes de continuar.")
            return
        try:
            resp = httpx.post(
                f"{API_BASE_URL}/projects/{project_id}/clarification",
                json={"answers": answers},
                timeout=15,
            )
            resp.raise_for_status()
            st.session_state["processing_start_time"] = time.time()
            st.rerun()
        except httpx.HTTPStatusError as e:
            st.error(f"API error: {e.response.text}")
        except httpx.ConnectError:
            st.error("Cannot connect to API")


def render_multiagent_completed(project: dict) -> None:
    """Render completed multiagent project: metrics, report, intermediates, per-agent table."""
    aggregated = project.get("metrics")
    if aggregated:
        st.divider()
        st.subheader("Metricas agregadas")
        render_metrics(aggregated)

    # Per-agent metrics table.
    agent_metrics = project.get("agent_metrics") or []
    if agent_metrics:
        st.subheader("Metricas por agente")
        import pandas as pd  # noqa: E402  (Streamlit already depends on pandas)

        rows = []
        for m in agent_metrics:
            rows.append({
                "Agente": str(m.get("agent") or "?"),
                "Provider": str(m.get("provider") or ""),
                "Modelo": str(m.get("model") or ""),
                "Tokens in": int(m.get("input_tokens") or 0),
                "Tokens out": int(m.get("output_tokens") or 0),
                "Tiempo (s)": round(float(m.get("execution_time_seconds") or 0), 2),
                "Coste ($)": round(float(m.get("estimated_cost_usd") or 0), 6),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Final markdown report.
    if project.get("markdown_content"):
        st.divider()
        render_report(project["markdown_content"], project["id"])

    # Per-agent raw outputs.
    outputs = project.get("agent_outputs") or {}
    if outputs:
        st.divider()
        st.subheader("Outputs intermedios por agente")
        for name in MULTIAGENT_AGENT_NAMES:
            content = outputs.get(name)
            if not content:
                continue
            with st.expander(f"Output de {MULTIAGENT_AGENT_LABELS[name]}"):
                st.code(content, language="json")

    # Clarification answers summary (if present).
    clar_answers = project.get("clarification_answers")
    if clar_answers:
        with st.expander("Respuestas a preguntas de clarificacion"):
            for q, a in clar_answers.items():
                st.markdown(f"- **{q}** → {a}")


# ── Main area ────────────────────────────────────────────────────────────────

if st.session_state["view"] == "detail":
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

    status = project.get("status", "completed")
    pipeline_type = project.get("pipeline_type", "baseline")

    if pipeline_type == "multiagent":
        st.title("Architecture Agent — Multiagente")
        st.caption("Pipeline de 4 agentes especializados con LangGraph")
    else:
        st.title("Architecture Agent — Baseline")
        st.caption("Single-agent baseline for automated software architecture design")

    st.subheader("Descripcion del proyecto")
    st.text(project["description"])

    if project.get("files"):
        st.subheader("Archivos adjuntos")
        for f in project["files"]:
            size_kb = f["size"] / 1024
            col_info, col_dl = st.columns([4, 1])
            with col_info:
                st.markdown(f"**{f['name']}** ({size_kb:.1f} KB)")
            with col_dl:
                try:
                    file_resp = httpx.get(
                        f"{API_BASE_URL}/projects/{project_id}/files/{f['file_id']}",
                        timeout=30,
                    )
                    file_resp.raise_for_status()
                    st.download_button(
                        label="Descargar",
                        data=file_resp.content,
                        file_name=f["name"],
                        mime=f["content_type"],
                        key=f"dl_file_{f['file_id']}",
                    )
                except Exception:
                    st.caption("Error al cargar")

    # ── Status-dependent rendering ───────────────────────────────────────

    if status == "processing":
        st.divider()
        if pipeline_type == "multiagent":
            render_processing_view_multiagent(project)
        else:
            render_processing_view_baseline(project)
        time.sleep(3)
        st.rerun()

    elif status == "waiting_clarification":
        render_clarification_form(project_id, project)

    elif status == "error":
        st.divider()
        st.error(f"El analisis ha fallado: {project.get('error_message', 'Error desconocido')}")

    elif status == "completed":
        st.session_state["processing_start_time"] = None
        if pipeline_type == "multiagent":
            render_multiagent_completed(project)
        else:
            if project.get("metrics"):
                st.divider()
                render_metrics(project["metrics"])
            if project.get("markdown_content"):
                render_report(project["markdown_content"], project_id)
        render_rating_form(project_id, project.get("ratings"))
        if project.get("markdown_content"):
            render_chat(project_id, project)

else:
    # ── Analyze view: tabs for mono / multi ──────────────────────────────
    st.title("Architecture Agent")
    st.caption("Genera informes de arquitectura con un solo agente (baseline) o con un pipeline multiagente.")

    tab_mono, tab_multi = st.tabs(["Monoagente", "Multiagente"])

    # Keep session_state.mode in sync with whichever tab the user touches.
    # Streamlit tabs don't fire a callback; we detect which one has widgets
    # interacted with via unique keys below.

    # ── Monoagente tab ───────────────────────────────────────────────────
    with tab_mono:
        if st.session_state["mode"] != "mono":
            if st.button("Activar modo monoagente (recargar selectores)", key="switch_to_mono"):
                st.session_state["mode"] = "mono"
                st.rerun()

        project_description_mono = st.text_area(
            "Project Description",
            height=250,
            placeholder=(
                "Describe your software project here. Include information about: "
                "what the system does, expected users, scale, team size, timeline, "
                "constraints, and any specific technology preferences..."
            ),
            key="desc_mono",
        )

        uploaded_files_mono = []
        if mono_provider == "ollama":
            st.info("La subida de archivos no esta disponible con el modelo local.")
        elif mono_provider:
            uploaded_files_mono = st.file_uploader(
                "Adjuntar archivos",
                accept_multiple_files=True,
                type=SUPPORTED_FILE_TYPES,
                help="Texto, PDFs e imagenes.",
                key="files_mono",
            ) or []

        mono_disabled = (
            st.session_state["mode"] != "mono"
            or not project_description_mono
            or health is None
            or not mono_model
        )
        if st.button(
            "Analyze (monoagente)",
            type="primary",
            disabled=mono_disabled,
            use_container_width=True,
            key="analyze_mono",
        ):
            form_data = {
                "description": project_description_mono,
                "provider": mono_provider,
                "model": mono_model,
            }
            files_to_upload = [
                ("files", (f.name, f.read(), f.type)) for f in uploaded_files_mono
            ]
            try:
                response = httpx.post(
                    f"{API_BASE_URL}/analyze/baseline",
                    data=form_data,
                    files=files_to_upload if files_to_upload else None,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
                st.session_state["view"] = "detail"
                st.session_state["selected_project_id"] = data["project_id"]
                st.session_state["processing_start_time"] = time.time()
                st.rerun()
            except httpx.HTTPStatusError as e:
                st.error(f"API error: {e.response.text}")
            except httpx.ConnectError:
                st.error(f"Cannot connect to API at {API_BASE_URL}")

    # ── Multiagente tab ──────────────────────────────────────────────────
    with tab_multi:
        if st.session_state["mode"] != "multi":
            if st.button("Activar modo multiagente (recargar selectores)", key="switch_to_multi"):
                st.session_state["mode"] = "multi"
                st.rerun()
            st.caption(
                "Al activar el modo multiagente, la barra lateral mostrara un selector "
                "por agente (o uno compartido si activas el toggle)."
            )

        project_description_multi = st.text_area(
            "Project Description",
            height=250,
            placeholder=(
                "Describe tu proyecto. Si la descripcion es ambigua, el Planner "
                "te hara algunas preguntas antes de continuar."
            ),
            key="desc_multi",
        )

        # Disable file upload if any selected agent uses Ollama.
        any_ollama_multi = any(
            cfg.get("provider") == "ollama" for cfg in multi_configs.values()
        )

        uploaded_files_multi = []
        if not multi_configs:
            st.info("Configura los modelos en la barra lateral.")
        elif any_ollama_multi:
            st.info(
                "La subida de archivos no esta disponible cuando algun agente usa Ollama."
            )
        else:
            uploaded_files_multi = st.file_uploader(
                "Adjuntar archivos",
                accept_multiple_files=True,
                type=SUPPORTED_FILE_TYPES,
                help="Texto, PDFs e imagenes (solo el Planner los usa).",
                key="files_multi",
            ) or []

        multi_disabled = (
            st.session_state["mode"] != "multi"
            or not project_description_multi
            or health is None
            or not multi_configs
        )
        if st.button(
            "Analyze (multiagente)",
            type="primary",
            disabled=multi_disabled,
            use_container_width=True,
            key="analyze_multi",
        ):
            form_data = {
                "description": project_description_multi,
                "planner_provider": multi_configs["planner"]["provider"],
                "planner_model": multi_configs["planner"]["model"],
                "requirements_provider": multi_configs["requirements"]["provider"],
                "requirements_model": multi_configs["requirements"]["model"],
                "designer_provider": multi_configs["designer"]["provider"],
                "designer_model": multi_configs["designer"]["model"],
                "validator_provider": multi_configs["validator"]["provider"],
                "validator_model": multi_configs["validator"]["model"],
            }
            files_to_upload = [
                ("files", (f.name, f.read(), f.type)) for f in uploaded_files_multi
            ]
            try:
                response = httpx.post(
                    f"{API_BASE_URL}/analyze/multiagent",
                    data=form_data,
                    files=files_to_upload if files_to_upload else None,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
                st.session_state["view"] = "detail"
                st.session_state["selected_project_id"] = data["project_id"]
                st.session_state["processing_start_time"] = time.time()
                st.rerun()
            except httpx.HTTPStatusError as e:
                st.error(f"API error: {e.response.text}")
            except httpx.ConnectError:
                st.error(f"Cannot connect to API at {API_BASE_URL}")
