# Documentacion Tecnica — Sistema Multiagente

> Pipeline de 4 agentes especializados con LangGraph para la generacion automatizada de informes de arquitectura de software.

---

## 1. Vision general

El sistema implementa dos modos de analisis de arquitectura:

| Modo | Agentes | Flujo | Feedback loop |
|------|---------|-------|---------------|
| **Baseline (monoagente)** | 1 (SingleAgent) | Descripcion -> Markdown directo | No |
| **Multiagente** | 4 (Planner, Requirements, Designer, Validator) | Descripcion -> Clarificacion (obligatoria) -> JSON pipeline -> Markdown consolidado | Si (max 2 revisiones) |

Ambos modos comparten la misma infraestructura (FastAPI, MongoDB, GridFS, LangGraph, Streamlit) y permiten seleccion de modelos por peticion entre OpenAI, Anthropic y Ollama (local).

Tras completarse el analisis, el usuario puede:
- **Evaluar el informe** con 7 criterios (0-10).
- **Chatear sobre el informe** con el modelo que elija (conversacion persistida).
- **Descargar el informe** en Markdown (.md) o PDF (.pdf).

---

## 2. Estructura del proyecto

```
TFG_AI-Software-Architecture-Agent/
|
|-- src/
|   |-- agents/                    # Logica de cada agente
|   |   |-- base.py                # BaseAgent: clase abstracta + helpers compartidos
|   |   |-- single_agent.py        # Baseline: un LLM call -> Markdown
|   |   |-- planner.py             # Planner: analisis + preguntas de clarificacion
|   |   |-- requirements_tech_stack.py  # Requisitos y stack tecnologico (JSON)
|   |   |-- architecture_designer.py   # Diseno de arquitectura (JSON)
|   |   |-- validator_aggregator.py    # Validacion + consolidacion final (JSON/Markdown)
|   |
|   |-- orchestration/             # Grafos LangGraph
|   |   |-- state.py               # PipelineState: TypedDict compartido entre agentes
|   |   |-- single_graph.py        # Grafo baseline: START -> SingleAgent -> END
|   |   |-- graph.py               # Grafos multiagente: planner + pipeline con feedback
|   |
|   |-- llm/                       # Capa de abstraccion LLM
|   |   |-- providers.py           # Factory: get_llm(provider, model) -> BaseChatModel
|   |   |-- models.py              # Catalogo de modelos disponibles + filtrado
|   |   |-- prompts.py             # System prompts + templates de usuario
|   |
|   |-- api/                       # FastAPI
|   |   |-- routes.py              # Endpoints REST + background tasks
|   |
|   |-- db/                        # Persistencia
|   |   |-- connection.py          # Motor async client + GridFS bucket
|   |   |-- repositories.py        # CRUD MongoDB: proyectos, ratings, archivos
|   |
|   |-- models/                    # Modelos Pydantic
|   |   |-- project.py             # ProjectDetail, ProjectSummary, AgentConfig, etc.
|   |   |-- metrics.py             # LLMMetrics, BaselineResult, MultiagentResult
|   |   |-- input.py               # ProjectInput, ClarificationResponse
|   |   |-- output.py              # MarkdownReport
|   |
|   |-- utils/                     # Utilidades
|   |   |-- cost.py                # Estimacion de coste por modelo
|   |   |-- file_processing.py     # Extraccion de texto (PDF/txt) + codificacion imagen
|   |   |-- logging.py             # Configuracion structlog
|   |   |-- pdf.py                 # Conversion Markdown -> PDF (fpdf2, pure Python)
|   |   |-- parsers.py             # Parsers auxiliares
|   |
|   |-- config.py                  # Settings (pydantic-settings), enums de entorno
|   |-- main.py                    # FastAPI app con lifespan
|
|-- frontend/
|   |-- app.py                     # Streamlit: tabs mono/multi, clarificacion, resultados
|
|-- docs/                          # Documentacion
|-- tests/                         # Tests (pytest-asyncio)
|-- docker-compose.yml             # api, frontend, mongodb, qdrant, ollama
|-- Dockerfile                     # Multi-stage: base -> api, base -> frontend
|-- pyproject.toml                 # Dependencias y configuracion
|-- .env.example                   # Variables de entorno
```

---

## 3. Arquitectura del sistema multiagente

### 3.1 Dos grafos separados

El pipeline multiagente se divide en **dos grafos LangGraph independientes** conectados via MongoDB:

#### Grafo 1: Planner (`build_planner_graph`)

```
START --> [PlannerAgent] --> END
```

- Analiza la descripcion del proyecto.
- **Siempre genera entre 3 y 5 preguntas de clarificacion** con opciones sugeridas (el flujo nunca las salta).
- Produce un `analysis_plan` que guia a los agentes posteriores.
- El backend guarda las preguntas + plan en MongoDB y pone el proyecto en estado `waiting_clarification`. El grafo termina y el pipeline queda a la espera de las respuestas del usuario.

#### Grafo 2: Pipeline (`build_pipeline_graph`)

```
START --> [RequirementsAgent] --> [DesignerAgent] --> [ValidatorAgent] -+-> END
               ^                                                       |
               |                    (revision_target="requirements")   |
               +-------------------------------------------------------+
                                        ^                              |
                                        |  (revision_target="designer")|
               [DesignerAgent] <---------------------------------------+
```

- **RequirementsAgent**: Extrae requisitos funcionales/no funcionales + recomienda stack.
- **DesignerAgent**: Disena la arquitectura (patron, componentes, diagrama Mermaid, riesgos, plan).
- **ValidatorAgent**: Valida coherencia. Puede:
  - Solicitar revision (max 2 veces) enviando feedback a Requirements o Designer.
  - Consolidar el informe final en Markdown.

La funcion `route_after_validation` decide el siguiente nodo:
- Si `markdown_content` esta lleno -> END (terminacion exitosa).
- Si `revision_target == "requirements"` -> vuelve a RequirementsAgent.
- Si `revision_target == "designer"` -> vuelve a DesignerAgent.

### 3.2 Separacion entre grafos via MongoDB

La razon de usar dos grafos en vez de uno con checkpoint de LangGraph:

1. **Pausa asincrona**: La clarificacion requiere interaccion del usuario (puede tardar minutos u horas). Un grafo LangGraph no puede "pausarse" esperando input externo.
2. **MongoDB como checkpoint**: El estado intermedio (planner output, preguntas, plan) se persiste en Mongo. Cuando el usuario responde, se crea un nuevo `asyncio.create_task` con el Grafo 2.
3. **Simplicidad**: No se necesita el checkpointer de LangGraph (complejidad extra sin beneficio claro aqui).

---

## 4. Flujo completo del pipeline multiagente

```
[Usuario]
    |
    | POST /analyze/multiagent
    | (descripcion + 4 pares provider/model + archivos)
    v
[API: analyze_multiagent()]
    |
    | 1. Valida modelos
    | 2. Crea proyecto en MongoDB (status=processing)
    | 3. asyncio.create_task(_run_planner_phase)
    | 4. Retorna {project_id, status=processing}
    v
[Background: _run_planner_phase()]
    |
    | Construye build_planner_graph()
    | Ejecuta PlannerAgent (SIEMPRE genera 3-5 preguntas)
    |
    | Guarda preguntas + plan en MongoDB
    | Status -> waiting_clarification
    | [FIN del task]
    |
    | [Frontend: poll detecta waiting_clarification]
    | [Frontend: muestra radio buttons con opciones + "Otro"]
    | [Usuario: responde]
    | POST /projects/{id}/clarification
    | API: submit_clarification_answers()
    |      asyncio.create_task(_run_pipeline_phase)
    v
[Background: _run_pipeline_phase()]
    |
    | Construye build_pipeline_graph()
    | Ejecuta con astream(stream_mode="values")
    |
    | Para cada evento del stream:
    |   - Actualiza current_step en MongoDB
    |   - Persiste agent_outputs nuevos
    |   - Sobreescribe agent_metrics completos
    |
    | [RequirementsAgent] -> JSON (requisitos + stack)
    | [DesignerAgent]     -> JSON (arquitectura + diagrama)
    | [ValidatorAgent]    -> JSON (revision o markdown final)
    |
    | Si revision necesaria (max 2):
    |   Loop back con revision_feedback
    |
    | Si markdown listo:
    |   repo.complete_multiagent_project()
    |   Status -> completed
    |
    v
[Frontend: poll detecta completed]
    |
    | Muestra:
    |   - Metricas agregadas (4 columnas)
    |   - Tabla de metricas por agente
    |   - Botones: Descargar .md / Descargar .pdf
    |   - Informe Markdown completo
    |   - Outputs intermedios (expandibles)
    |   - Formulario de evaluacion (7 criterios 0-10)
    |   - Chat sobre el informe (selector de modelo + conversacion)
```

---

## 5. Detalle de cada agente

### 5.1 BaseAgent (`src/agents/base.py`)

Clase abstracta que define la interfaz comun y los helpers compartidos:

| Metodo | Tipo | Descripcion |
|--------|------|-------------|
| `name` | property (abstract) | Nombre del agente para logging |
| `run(state)` | async (abstract) | Ejecuta la tarea y retorna partial state update |
| `_invoke_and_measure(system_prompt, user_content)` | async | Invoca LLM, mide tokens/tiempo/coste, retorna `(raw_text, metrics_dict)` |
| `_extract_tokens(raw_message)` | sync | Extrae tokens de `usage_metadata` (OpenAI/Anthropic) o `response_metadata` (Ollama) |
| `_parse_json_output(raw_text)` | sync | Parsea JSON tolerando code fences, whitespace, prosa alrededor |

### 5.2 SingleAgent (`src/agents/single_agent.py`) — Baseline

- **Input**: `project_description`, `user_documents`, `user_images`
- **Prompt**: `SINGLE_AGENT_SYSTEM_PROMPT` (instrucciones para producir Markdown con 7 secciones)
- **Output**: Markdown directo (NO JSON)
- **Metodo extra**: `_extract_markdown()` — quita fences ```markdown que algunos modelos anaden

### 5.3 PlannerAgent (`src/agents/planner.py`)

- **Input**: `project_description`, `user_documents`, `user_images`
- **Prompt**: `PLANNER_SYSTEM_PROMPT`
- **Output JSON**:
  ```json
  {
    "questions": [{"question": "...", "options": ["A", "B", "C"]}],
    "analysis_plan": {
      "summary": "...",
      "key_concerns": ["..."],
      "recommended_focus": "...",
      "assumptions": ["..."]
    }
  }
  ```
- **Comportamiento**: SIEMPRE produce entre 3 y 5 preguntas de clarificacion + `analysis_plan`. No hay rama opcional: el pipeline siempre pasa por la fase de clarificacion.

### 5.4 RequirementsTechStackAgent (`src/agents/requirements_tech_stack.py`)

- **Input**: `project_description`, `analysis_plan`, `clarification_answers`, (opcionalmente `revision_feedback` si `revision_target == "requirements"`)
- **Prompt**: `REQUIREMENTS_SYSTEM_PROMPT`
- **Output JSON**:
  ```json
  {
    "functional_requirements": [{"priority": "MUST|SHOULD|NICE", "description": "..."}],
    "non_functional_requirements": [...],
    "tech_stack": [{"category": "...", "name": "...", "justification": "...", "pros": [...], "cons": [...], "alternatives": [...]}],
    "notes": "..."
  }
  ```
- **Comportamiento en revision**: Si recibe `revision_feedback`, lo incluye en el prompt y limpia los campos de revision tras consumirlos.

### 5.5 ArchitectureDesignerAgent (`src/agents/architecture_designer.py`)

- **Input**: `project_description`, `analysis_plan`, `clarification_answers`, `agent_outputs["requirements"]` (JSON raw del agente anterior), (opcionalmente `revision_feedback` si `revision_target == "designer"`)
- **Prompt**: `DESIGNER_SYSTEM_PROMPT`
- **Output JSON**:
  ```json
  {
    "architectural_pattern": {"name": "...", "justification": "..."},
    "components": [{"name": "...", "technology": "...", "responsibility": "...", "communicates_with": [...]}],
    "design_patterns": [{"name": "...", "justification": "..."}],
    "mermaid_diagram": "graph TD\\n...",
    "infrastructure": "...",
    "risks": [{"severity": "ALTO|MEDIO|BAJO", "title": "...", "description": "...", "mitigation": "..."}],
    "development_phases": [{"name": "...", "duration": "...", "description": "...", "deliverables": [...], "dependencies": [...]}]
  }
  ```

### 5.6 ValidatorAggregatorAgent (`src/agents/validator_aggregator.py`)

- **Input**: `project_description`, `analysis_plan`, `clarification_answers`, `agent_outputs["requirements"]`, `agent_outputs["designer"]`, `revision_count`
- **Prompt**: `VALIDATOR_SYSTEM_PROMPT`
- **Output JSON**:
  ```json
  {
    "needs_revision": true/false,
    "revision_target": "requirements" | "designer" | "",
    "revision_feedback": "feedback accionable...",
    "markdown_content": "# Informe completo..." | ""
  }
  ```
- **Logica de decision**:
  - Si `revision_count >= 2`: **forzar terminacion** (`needs_revision = false`), producir `markdown_content` aunque haya problemas (se listan en seccion de Riesgos).
  - Si `needs_revision == true`: `markdown_content` se deja vacio (la presencia de markdown es la senal de terminacion del grafo).
  - Si `needs_revision == false`: `markdown_content` contiene el informe Markdown completo consolidado.

---

## 6. PipelineState — Estado compartido

Definido en `src/orchestration/state.py` como `TypedDict(total=False)`:

```python
class PipelineState(TypedDict, total=False):
    # --- Input del usuario ---
    project_description: str
    user_documents: list[str]          # Texto extraido de archivos
    user_images: list[dict]            # {mime_type, base64_data}
    session_id: str

    # --- Contexto multiagente ---
    project_id: str                    # ID de MongoDB
    current_step: str                  # Para el progreso en frontend
    agent_configs: dict[str, dict]     # {"planner": {"provider":"openai","model":"gpt-4o"}, ...}

    # --- Clarificacion ---
    clarification_questions: list[dict]  # [{"question":"...", "options":["A","B"]}]
    clarification_answers: dict[str, str]

    # --- Outputs de agentes ---
    analysis_plan: dict[str, Any]
    requirements: dict[str, Any]
    tech_stack: dict[str, Any]
    architecture: dict[str, Any]
    validation_results: dict[str, Any]
    markdown_content: str              # Informe final (vacio durante revision)

    # --- Control del feedback loop ---
    revision_count: int                # 0, 1, o 2
    revision_target: str               # "" | "requirements" | "designer"
    revision_feedback: str             # Texto del Validator con issues a corregir

    # --- Metricas por agente ---
    agent_outputs: dict[str, str]      # {"planner": "raw json", "requirements": "raw json", ...}
    agent_metrics: list[dict]          # Lista de LLMMetrics dicts

    # --- Agregado ---
    metrics: dict[str, Any]            # Metricas del baseline (o agregadas multi)
    errors: list[str]
```

**Nota**: `total=False` significa que LangGraph no requiere que todos los campos esten presentes en el estado inicial. Cada agente retorna un **partial state update** que LangGraph mergea con el estado existente (por reemplazo de clave, no deep merge).

---

## 7. API REST

### 7.1 Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/health` | Estado del servicio, entorno, proveedor LLM |
| `GET` | `/models` | Modelos disponibles (filtrados por entorno/API keys) |
| `POST` | `/analyze/baseline` | Iniciar analisis monoagente (FormData) |
| `POST` | `/analyze/multiagent` | Iniciar analisis multiagente (FormData con 8 campos de modelo) |
| `POST` | `/projects/{id}/clarification` | Enviar respuestas de clarificacion (JSON) |
| `GET` | `/projects` | Listar proyectos (sidebar del historial) |
| `GET` | `/projects/{id}` | Detalle completo de un proyecto |
| `DELETE` | `/projects/{id}` | Eliminar proyecto y sus archivos GridFS |
| `PUT` | `/projects/{id}/ratings` | Guardar evaluacion (7 criterios 0-10) |
| `GET` | `/projects/{id}/files/{fid}` | Descargar archivo de GridFS |
| `GET` | `/projects/{id}/download/pdf` | Descargar el informe final como PDF (generado on-the-fly) |
| `POST` | `/projects/{id}/chat` | Enviar mensaje al chat post-generacion (JSON `{message, provider, model}`) |

### 7.2 Background tasks

Todas las tareas de analisis se ejecutan con `asyncio.create_task()` para no bloquear la respuesta HTTP:

- **`_run_analysis()`**: Baseline. Construye `single_agent_graph`, invoca, persiste resultado.
- **`_run_planner_phase()`**: Multiagente fase 1. Ejecuta PlannerAgent. Siempre persiste preguntas + plan en MongoDB y deja el proyecto en `waiting_clarification`. Nunca encadena directamente al pipeline.
- **`_run_pipeline_phase()`**: Multiagente fase 2. Lanzado tras recibir las respuestas del usuario. Ejecuta el pipeline con `astream()` para persistir progreso en tiempo real.

### 7.3 Streaming y persistencia en tiempo real

`_run_pipeline_phase` usa `graph.astream(initial_state, stream_mode="values")` que emite el estado completo tras cada nodo. Para cada evento:

1. `repo.update_current_step()` — actualiza el paso actual en MongoDB.
2. `repo.save_agent_output()` — guarda outputs nuevos (delta detection via `seen_outputs`).
3. `repo.save_agent_metrics()` — sobreescribe la lista completa (evita duplicacion del `$push`).

---

## 8. Persistencia (MongoDB)

### 8.1 Documento de proyecto

```javascript
{
  "_id": ObjectId("..."),
  "created_at": ISODate("..."),
  "description": "...",
  "provider": "openai",              // Del planner en multiagente
  "model": "gpt-4o",
  "pipeline_type": "baseline" | "multiagent",
  "status": "processing" | "waiting_clarification" | "completed" | "error",
  "current_step": "planner" | "requirements" | "designer" | "validator" | ...,
  "error_message": null | "...",

  // Configuracion de agentes (solo multiagente)
  "agent_configs": {
    "planner": {"provider": "openai", "model": "gpt-4o"},
    "requirements": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
    "designer": {"provider": "openai", "model": "gpt-4o-mini"},
    "validator": {"provider": "openai", "model": "gpt-4o"}
  },

  // Archivos adjuntos (GridFS refs)
  "files": [{"file_id": "...", "name": "...", "size": 1234, "content_type": "..."}],

  // Datos procesados para el LLM (solo multiagente, para resume tras clarificacion)
  "processed_documents": ["texto extraido..."],
  "processed_images": [{"mime_type": "image/png", "base64_data": "..."}],

  // Clarificacion
  "clarification_questions": [{"question": "...", "options": ["A", "B"]}],
  "clarification_answers": {"pregunta": "respuesta"},
  "analysis_plan": {"summary": "...", ...},

  // Outputs intermedios
  "agent_outputs": {
    "planner": "{raw json}",
    "requirements": "{raw json}",
    "designer": "{raw json}",
    "validator": "{raw json}"
  },
  "agent_metrics": [
    {"provider": "openai", "model": "gpt-4o", "input_tokens": 500, ..., "agent": "Planner"},
    ...
  ],

  // Resultado final
  "markdown_content": "# Resumen Ejecutivo\n...",
  "metrics": {"provider": "multiagent", "model": "multiple", "input_tokens": 5000, ...},
  "ratings": {"identifies_right_concerns": 8, ..., "comments": "..."},

  // Chat post-generacion (null hasta el primer mensaje)
  "chat_history": [
    {
      "role": "user" | "assistant",
      "content": "...",
      "timestamp": ISODate("..."),
      "metrics": {"provider": "...", "model": "...", "input_tokens": ..., ...} | null
    }
  ]
}
```

### 8.2 Funciones principales de repositorio

| Funcion | Descripcion |
|---------|-------------|
| `create_project()` | Crea proyecto baseline con archivos en GridFS |
| `create_multiagent_project()` | Crea proyecto multiagente con configs + docs/images procesados |
| `complete_project()` | Marca baseline como completado |
| `complete_multiagent_project()` | Marca multiagente como completado con metricas agregadas |
| `fail_project()` | Marca como error |
| `update_current_step()` | Actualiza progreso (para polling del frontend) |
| `set_clarification_questions()` | Guarda preguntas + plan, status -> waiting_clarification |
| `submit_clarification_answers()` | Guarda respuestas, status -> processing |
| `save_agent_output()` | `$set` en `agent_outputs.{name}` |
| `save_agent_metrics()` | `$set` completo de `agent_metrics` (evita duplicacion) |
| `list_projects()` | Listado para sidebar con preview de descripcion |
| `get_project()` | Documento completo por ID |
| `delete_project()` | Elimina proyecto + archivos GridFS |
| `update_ratings()` | Guarda evaluacion |
| `append_chat_messages()` | `$push` atomico con `$each` de mensajes user+assistant al `chat_history` |
| `get_project_file()` | Stream de GridFS para descarga |

---

## 9. Prompts del sistema

### 9.1 Estrategia

- **Idioma de los prompts**: Ingles (los modelos siguen instrucciones mejor en ingles).
- **Idioma del output**: Castellano (todo el texto visible para el usuario).
- **Formato de output**: JSON estricto (sin code fences alrededor del JSON).
- **Schema forzado**: Cada prompt especifica el schema JSON exacto que el modelo debe producir.

### 9.2 Prompts disponibles

| Constante | Agente | Descripcion |
|-----------|--------|-------------|
| `SINGLE_AGENT_SYSTEM_PROMPT` | SingleAgent | Genera Markdown con 7 secciones |
| `PLANNER_SYSTEM_PROMPT` | Planner | Analiza la descripcion y SIEMPRE produce 3-5 preguntas + plan |
| `REQUIREMENTS_SYSTEM_PROMPT` | Requirements | Requisitos funcionales/no funcionales + stack |
| `DESIGNER_SYSTEM_PROMPT` | Designer | Arquitectura + diagrama + riesgos + plan desarrollo |
| `VALIDATOR_SYSTEM_PROMPT` | Validator | Valida o consolida informe final |
| `CHAT_SYSTEM_PROMPT` | Chat post-generacion | Asistente conversacional con el `markdown_content` inyectado como contexto |

### 9.3 Helpers de formato

| Funcion | Uso |
|---------|-----|
| `format_user_message()` | Baseline: descripcion + documentos + imagenes |
| `format_multiagent_user_message()` | Multiagente: descripcion + documentos + imagenes + clarificacion + plan + outputs anteriores + feedback |

`format_multiagent_user_message()` es clave: cada agente recibe SOLO el contexto que necesita. La funcion incluye condicionalmente:
- Documentos adicionales
- Respuestas de clarificacion
- Plan del Planner (JSON)
- Output de Requirements (JSON)
- Output de Designer (JSON)
- Feedback de revision
- revision_count actual

---

## 10. Frontend (Streamlit)

### 10.1 Estructura de vistas

```
app.py
|
|-- Sidebar
|   |-- Health check
|   |-- Model selector (mono: 1 selectbox / multi: 1 o 4 selectboxes)
|   |-- Historial de proyectos ([B]/[M] badges, status icons)
|
|-- Main area
    |-- Vista "analyze" (por defecto)
    |   |-- Tab "Monoagente"
    |   |   |-- Text area + file uploader + boton Analyze
    |   |-- Tab "Multiagente"
    |       |-- Text area + file uploader + boton Analyze
    |
    |-- Vista "detail" (al seleccionar un proyecto)
        |-- Descripcion + archivos adjuntos
        |-- Segun status:
            |-- processing: barra de progreso + current_step (multi) o mensajes (mono)
            |-- waiting_clarification: radio buttons con opciones + boton continuar
                (en multiagente, aparece SIEMPRE tras la fase Planner)
            |-- error: mensaje de error
            |-- completed:
                |-- Baseline: metricas + botones descarga (.md / .pdf) + markdown + evaluacion + chat
                |-- Multiagente: metricas agregadas + tabla por agente + botones descarga (.md / .pdf) + markdown + intermedios + evaluacion + chat
```

### 10.2 Polling

El frontend usa `time.sleep(3) + st.rerun()` para sondear el estado de proyectos en `processing`. Cuando el estado cambia a `completed` o `error`, deja de sondear.

### 10.3 Seleccion de modelos multiagente

- **Toggle "Usar el mismo modelo para todos"**: Un solo selectbox que aplica a los 4 agentes.
- **Sin toggle**: 4 selectboxes independientes (uno por agente), permitiendo mezcla libre de proveedores.

### 10.4 Clarificacion

La fase de clarificacion siempre ocurre en el flujo multiagente:
1. Frontend detecta `status == "waiting_clarification"`.
2. Renderiza `st.radio` con las opciones del Planner + "Otro (escribir abajo)".
3. Si el usuario elige "Otro", aparece un `st.text_input`.
4. Al pulsar "Continuar analisis", POST a `/projects/{id}/clarification`.

### 10.5 Descarga en PDF

En la vista `completed`, `render_report()` muestra dos botones en columnas paralelas:
- **Descargar .md**: `st.download_button` con el `markdown_content` directo.
- **Descargar .pdf**: Hace GET a `/projects/{id}/download/pdf` (genera el PDF on-the-fly desde `markdown_content` con fpdf2) y expone los bytes via `st.download_button`.

La generacion del PDF vive en [src/utils/pdf.py](../src/utils/pdf.py):
- `markdown_to_pdf(md) -> bytes` — entrada principal, pure Python (sin dependencias del sistema).
- `_preprocess_mermaid()` — transforma bloques ```mermaid en "Diagrama (fuente Mermaid):" + codigo plano (no se renderiza el diagrama).
- `_sanitize()` — reemplaza caracteres Unicode no soportados por Helvetica/Courier (comillas tipograficas, guiones em/en, flechas, simbolos matematicos, elipsis, bullets, box-drawing) por equivalentes ASCII; fallback NFKD para el resto.
- Helpers de render: `_render_heading`, `_render_paragraph`, `_render_list_item`, `_render_code_block`, `_render_table_row`, `_strip_inline`.

### 10.6 Chat sobre el informe

En la vista `completed`, `render_chat(project_id, project)` aparece tras el formulario de evaluacion:
1. Selector inline de proveedor/modelo (defaults al modelo del analisis via `_find_model_index`).
2. Historial renderizado con `st.chat_message("user")` / `st.chat_message("assistant")` en loop.
3. `st.chat_input("Pregunta algo sobre el informe...")` como caja de entrada.
4. Al enviar: POST a `/projects/{id}/chat` con `{message, provider, model}` -> `st.rerun()` refresca el hilo.

El chat NO es un agente del pipeline ni pasa por LangGraph. Es una llamada directa a `get_llm(provider, model).ainvoke(messages)` donde `messages` es:
- `SystemMessage(CHAT_SYSTEM_PROMPT.format(markdown_content=...))`
- Historial previo mapeado a `HumanMessage` / `AIMessage`
- El nuevo `HumanMessage` del usuario

El endpoint extrae tokens, construye el `ChatMessage` del assistant con sus metricas, y hace `$push $each` atomico de ambos (user + assistant) sobre `chat_history`.

---

## 11. Proveedores LLM

### 11.1 Modelos disponibles

| Provider | Modelo | Tier | Vision |
|----------|--------|------|--------|
| OpenAI | gpt-4o-mini | economic | Si |
| OpenAI | gpt-5.2 | performance | Si |
| Anthropic | claude-haiku-4-5 | economic | Si |
| Anthropic | claude-sonnet-4-6 | performance | Si |
| Ollama | configurable (.env) | local | No |

### 11.2 Mezcla libre

En multiagente, cada agente puede usar un proveedor/modelo distinto. Ejemplo:
- Planner: `openai/gpt-4o-mini` (rapido para analisis inicial)
- Requirements: `anthropic/claude-sonnet-4-6` (razonamiento profundo)
- Designer: `openai/gpt-4o-mini` (generacion de diagrama)
- Validator: `anthropic/claude-sonnet-4-6` (validacion critica)

### 11.3 Estimacion de costes

`src/utils/cost.py` tiene un diccionario `COST_PER_1K_TOKENS` con precios input/output por modelo. Ollama siempre devuelve coste $0.00.

---

## 12. Configuracion y despliegue

### 12.1 Docker Compose

```bash
# Desarrollo local (con Ollama GPU)
docker compose --profile local up --build

# Sin Ollama (solo APIs cloud)
docker compose up --build
```

**Servicios**:
- `api` (puerto 8000): FastAPI con hot-reload via volumen `./src:/app/src`
- `frontend` (puerto 8501): Streamlit (requiere rebuild para cambios)
- `mongodb` (puerto 27017): Persistencia de proyectos
- `qdrant` (puerto 6333): Vector DB (reservado para futuro RAG)
- `ollama` (puerto 11434): LLM local con soporte GPU (profile: local)

### 12.2 Variables de entorno clave

```env
# Proveedores LLM
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://ollama:11434

# Base de datos
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DATABASE=tfg_architect

# Observabilidad
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=lsv2_...
```

---

## 13. Guia para extender el sistema

### 13.1 Anadir un nuevo agente

1. Crear `src/agents/nuevo_agente.py` con clase que herede de `BaseAgent`.
2. Implementar `name` property y `run(state)` que retorne partial state update.
3. Anadir su system prompt en `src/llm/prompts.py`.
4. Registrar el nodo en `src/orchestration/graph.py` (`build_pipeline_graph`).
5. Anadir su config en `src/models/project.py` (`MultiagentConfigs`).
6. Actualizar el endpoint `POST /analyze/multiagent` en `routes.py`.
7. Actualizar el frontend para el nuevo selector de modelo.

### 13.2 Modificar el feedback loop

- `route_after_validation()` en `graph.py` controla la logica de routing.
- `revision_count` se incrementa en `ValidatorAggregatorAgent.run()`.
- El limite de 2 revisiones esta en el Validator (safety net) y en el prompt.

### 13.3 Anadir un nuevo proveedor LLM

1. Instalar el paquete LangChain correspondiente (`langchain-{provider}`).
2. Anadir caso en `src/llm/providers.py` (`get_llm`).
3. Anadir modelos en `src/llm/models.py` (`MODEL_CATALOG`).
4. Anadir precios en `src/utils/cost.py`.
5. Anadir settings en `src/config.py`.

### 13.4 Cambiar el formato de output de un agente

1. Modificar el system prompt en `prompts.py`.
2. Adaptar el parsing en el metodo `run()` del agente (tras `_parse_json_output()`).
3. Si cambia la estructura del state, actualizar `PipelineState` en `state.py`.

### 13.5 Cambiar las secciones del informe final

Las 7 secciones del informe estan definidas en:
- `SINGLE_AGENT_SYSTEM_PROMPT` (baseline)
- `VALIDATOR_SYSTEM_PROMPT` (multiagente — seccion "Final Markdown structure")

Ambos deben actualizarse en paralelo para mantener consistencia entre modos.

---

## 14. Decisiones de diseno

| Decision | Alternativa considerada | Razon |
|----------|------------------------|-------|
| Dos grafos separados | Un grafo con checkpointer | La pausa para clarificacion es asincrona y puede durar horas |
| MongoDB como checkpoint | LangGraph checkpointer | Simplicidad; el proyecto ya usa MongoDB |
| JSON estricto entre agentes | Markdown o texto libre | Permite parsing determinista y routing condicional |
| `astream` con persistencia | `ainvoke` sin streaming | Permite actualizar progreso en tiempo real |
| `$set` para metrics (no `$push`) | `$push` incremental | `astream` emite el estado completo; `$push` duplicaba metricas |
| Prompts en ingles, output en espanol | Todo en espanol | Mejores resultados de adherencia a instrucciones en ingles |
| `total=False` en PipelineState | Campos obligatorios | Cada agente solo necesita un subconjunto del estado |
| Clarificacion siempre obligatoria | Clarificacion opcional (decision del Planner) | Flujo mas predecible; el usuario siempre valida asunciones antes de pasar al pipeline caro |
| `fpdf2` para PDF (pure Python) | `xhtml2pdf`/`weasyprint` | Sin dependencias del sistema (libpango/libcairo); evita romper el build de Docker |
| Chat como llamada LLM directa | Chat como agente LangGraph | El chat no necesita herramientas ni routing; inyectar el markdown en el system prompt es suficiente y mas barato |
| `ChatMessage` con `metrics` opcional | Solo texto | Permite auditar coste/tiempo tambien del chat post-generacion |
| `$push $each` atomico para mensajes | Dos writes separados | Garantiza que user+assistant aparecen juntos o no aparecen (consistencia) |
