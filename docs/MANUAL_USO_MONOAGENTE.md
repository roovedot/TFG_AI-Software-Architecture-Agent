# Manual Tecnico — Sistema Monoagente (Baseline)

Estado del proyecto: **Fase 1 completada** — Sistema monoagente baseline funcional.

---

## 1. Estructura del proyecto

```
.
├── docker-compose.yml          # Orquestacion de servicios (api, frontend, mongodb, ollama)
├── Dockerfile                  # Multi-stage build (target: api | frontend)
├── pyproject.toml              # Dependencias, config de ruff y pytest
├── .env                        # Configuracion unica (local o production)
│
├── src/                        # Codigo fuente principal
│   ├── config.py               # Configuracion centralizada (lee de .env)
│   ├── main.py                 # Entry point FastAPI
│   │
│   ├── agents/
│   │   ├── base.py             # Clase abstracta BaseAgent
│   │   ├── single_agent.py     # ** Agente monoagente (baseline) **
│   │   ├── planner.py          # [Fase 2] Agente planificador
│   │   ├── requirements_tech_stack.py  # [Fase 2]
│   │   ├── architecture_designer.py    # [Fase 2]
│   │   └── validator_aggregator.py     # [Fase 2]
│   │
│   ├── api/
│   │   └── routes.py           # Endpoints: /health, /models, /analyze/baseline, /projects/*
│   │
│   ├── db/
│   │   ├── connection.py       # Cliente MongoDB singleton + GridFS bucket
│   │   └── repositories.py     # CRUD de proyectos + almacenamiento GridFS
│   │
│   ├── llm/
│   │   ├── providers.py        # Factory get_llm() -> OpenAI | Anthropic | Ollama
│   │   ├── prompts.py          # Prompt del monoagente + format_user_message (multimodal)
│   │   └── models.py           # Catalogo de modelos disponibles
│   │
│   ├── models/
│   │   ├── input.py            # ProjectInput (validacion de entrada)
│   │   ├── output.py           # MarkdownReport
│   │   ├── metrics.py          # LLMMetrics, BaselineResult
│   │   └── project.py          # ProjectDetail, ProjectSummary, ProjectRating, AnalyzeResponse
│   │
│   ├── orchestration/
│   │   ├── state.py            # PipelineState (estado compartido del grafo)
│   │   ├── single_graph.py     # Grafo LangGraph de 1 nodo (baseline)
│   │   └── graph.py            # [Fase 2] Grafo multiagente
│   │
│   └── utils/
│       ├── logging.py          # Configuracion de structlog
│       ├── cost.py             # Estimacion de coste por proveedor/modelo
│       ├── file_processing.py  # Procesamiento de archivos (PDF, texto, imagenes)
│       └── parsers.py          # [Fase 2] Parsers auxiliares
│
├── frontend/
│   ├── app.py                  # UI Streamlit (input + historial + evaluacion + resultados)
│   └── static/                 # Assets estaticos (placeholder)
│
├── tests/                      # Tests (vacios, pendientes de implementar)
│
├── data/
│   ├── knowledge_base/         # [Fase 2] Corpus para RAG
│   └── test_cases/             # Casos de prueba de ejemplo
│
├── notebooks/experiments/      # Jupyter notebooks de experimentacion
└── docs/
    ├── PUNTO_DE_PARTIDA.md     # Documento de vision del proyecto
    └── resultados/             # Informes de arquitectura generados como ejemplo/referencia
```

Archivos marcados con `[Fase 2]` estan creados como placeholders y se implementaran en la fase multiagente.

---

## 2. Requisitos previos

- **Docker** y **Docker Compose** (v2+)
- **Python 3.11+** (solo si quieres ejecutar fuera de Docker)
- **uv** (solo si quieres gestionar dependencias localmente: `pip install uv`)

---

## 3. Configuracion del entorno

El proyecto usa un unico archivo `.env` para toda la configuracion.

### 3.1. Crear el archivo .env

Copia y edita el archivo con tu configuracion:

```bash
cp .env.example .env   # si existe .env.example
```

### 3.2. Configurar .env

El archivo `.env` contiene todas las opciones. Las mas importantes:

```env
# ENVIRONMENT=local       → despliega Ollama (docker compose --profile local up)
# ENVIRONMENT=production  → solo APIs de pago (docker compose up)
ENVIRONMENT=local

# Rellenar para usar modelos cloud
OPENAI_API_KEY=sk-...tu-clave...
ANTHROPIC_API_KEY=sk-ant-...tu-clave...

# Modelo local (Ollama)
OLLAMA_MODEL=llama3.2:3b

# MongoDB (persistencia de proyectos)
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DATABASE=tfg_architect
```

Los modelos disponibles se configuran por la presencia de API keys:
- Si `OPENAI_API_KEY` tiene valor → modelos de OpenAI disponibles en el frontend
- Si `ANTHROPIC_API_KEY` tiene valor → modelos de Anthropic disponibles
- Si `ENVIRONMENT=local` → modelo de Ollama disponible

---

## 4. Levantar el proyecto con Docker

### 4.1. Entorno local (con Ollama)

```bash
docker compose --profile local up --build
```

Esto levanta 5 servicios:

| Servicio | Puerto | Descripcion |
|----------|--------|-------------|
| `api` | 8000 | Backend FastAPI |
| `frontend` | 8501 | UI Streamlit |
| `mongodb` | 27017 | Base de datos (persistencia de proyectos y archivos) |
| `ollama` | 11434 | LLM local (solo con `--profile local`) |

La primera vez que levantes Ollama, necesitas descargar el modelo:

```bash
docker compose --profile local exec ollama ollama pull llama3.2:3b
```

### 4.2. Entorno de produccion (con APIs, sin Ollama)

Cambia `ENVIRONMENT=production` en `.env`, y luego:

```bash
docker compose up --build
```

Levanta 3 servicios (sin Ollama): `api`, `frontend`, `mongodb`.

### 4.3. Parar todo

```bash
docker compose --profile local down       # local
docker compose down                       # prod
```

Para borrar tambien los volumenes (datos de MongoDB y modelos de Ollama):

```bash
docker compose --profile local down -v
```

---

## 5. Uso del sistema

### 5.1. Verificar que la API funciona

```bash
curl http://localhost:8000/health
```

Respuesta esperada:

```json
{
  "status": "ok",
  "environment": "local",
  "llm_provider": "ollama"
}
```

### 5.2. Consultar modelos disponibles

```bash
curl http://localhost:8000/models
```

Devuelve la lista de modelos disponibles segun el entorno y las API keys configuradas.

### 5.3. Usar desde el frontend (Streamlit)

1. Abre http://localhost:8501 en el navegador.
2. Verifica que la sidebar muestre "API connected" y los modelos disponibles.
3. **Selecciona un modelo** del desplegable en la sidebar.
4. Escribe una descripcion de proyecto en el text area. Ejemplo:

   > An e-commerce platform for a small business selling handmade crafts online. Needs user authentication, product catalog, shopping cart, payment processing, and order management. Expected around 1000 concurrent users. Team of 3 developers, 6-month timeline. Budget is limited, prefer open-source solutions.

5. **(Opcional) Adjunta archivos** arrastrando o haciendo click en la zona de upload:
   - **Texto**: .txt, .md, .csv, .json, .xml, .yaml, .py, .js, etc.
   - **PDFs**: se extrae el texto automaticamente
   - **Imagenes**: .png, .jpg, .gif, .webp — se envian al modelo como contenido visual (solo modelos cloud con vision)
   - **Nota**: La subida de archivos no esta disponible con el modelo local (Ollama).

6. Pulsa "Analyze".
7. El proyecto se crea inmediatamente en MongoDB y aparece en el historial de la sidebar con estado `...` (procesando). La API ejecuta el analisis en segundo plano.
8. La vista de detalle muestra un cronometro y mensajes de progreso. Puedes navegar a otros proyectos del historial mientras el analisis se ejecuta — el resultado aparecera automaticamente cuando termine.
9. Una vez completado, se muestra el documento Markdown renderizado, la barra de metricas (tiempo, tokens, coste) y el boton "Descargar .md" para exportar.
10. **(Opcional) Evalua el resultado** con el formulario de puntuacion (7 criterios, 0-10).

### 5.4. Historial de proyectos

Cada analisis se guarda automaticamente como un **proyecto** en MongoDB. El historial se muestra en la barra lateral izquierda.

- **Ver un proyecto anterior**: haz click en la entrada del historial.
- **Evaluar un proyecto**: en la vista de detalle, usa los sliders (0-10) para cada criterio y pulsa "Guardar evaluacion".
- **Eliminar un proyecto**: pulsa el boton "x" junto a la entrada. Se eliminan el proyecto y sus archivos adjuntos de MongoDB.

Indicadores de estado en el historial:
- `...` — analisis en proceso
- `ERR` — el analisis fallo
- `*` — el proyecto tiene evaluacion guardada
- (sin indicador) — completado, sin evaluar

Los 7 criterios de evaluacion son:

| # | Criterio | Descripcion |
|---|----------|-------------|
| 1 | Identifica las preocupaciones correctas | ¿Aborda las cuestiones arquitectonicas relevantes? |
| 2 | Se ajusta a lo pedido | ¿Respeta la descripcion y no inventa cosas? |
| 3 | Completitud del analisis tecnico | ¿Cubre escalabilidad, seguridad, datos, despliegue? |
| 4 | Calidad de la recomendacion tecnologica | ¿Stack apropiado y factible? |
| 5 | Claridad y estructura del documento | ¿Bien organizado y legible? |
| 6 | Identificacion de riesgos | ¿Riesgos relevantes con mitigaciones? |
| 7 | Plan de desarrollo accionable | ¿Un equipo podria empezar a implementar con esto? |

### 5.5. Usar directamente desde la API (curl)

El endpoint de analisis es **asincrono**: devuelve inmediatamente un `project_id` y ejecuta el analisis en segundo plano.

```bash
curl -X POST http://localhost:8000/analyze/baseline \
  -F "description=An e-commerce platform for selling books online. Team of 2 developers, 3 month timeline." \
  -F "provider=openai" \
  -F "model=gpt-4o-mini"
```

Respuesta inmediata:

```json
{
  "project_id": "683d...",
  "status": "processing"
}
```

Con archivos adjuntos:

```bash
curl -X POST http://localhost:8000/analyze/baseline \
  -F "description=An e-commerce platform." \
  -F "provider=openai" \
  -F "model=gpt-4o-mini" \
  -F "files=@requirements.pdf" \
  -F "files=@mockup.png"
```

Para consultar el resultado, hacer polling al detalle del proyecto:

```bash
curl http://localhost:8000/projects/{project_id}
```

Cuando `status` sea `"completed"`, la respuesta incluye `markdown_content` y `metrics`:

```json
{
  "id": "683d...",
  "status": "completed",
  "description": "...",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "markdown_content": "## 1. Resumen Ejecutivo\n...",
  "metrics": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "input_tokens": 1523,
    "output_tokens": 2847,
    "total_tokens": 4370,
    "execution_time_seconds": 12.453,
    "estimated_cost_usd": 0.001937
  },
  "files": [...],
  "ratings": null,
  "created_at": "2026-03-22T..."
}
```

### 5.6. API de proyectos (curl)

```bash
# Listar todos los proyectos
curl http://localhost:8000/projects

# Ver detalle de un proyecto
curl http://localhost:8000/projects/{project_id}

# Eliminar un proyecto (y sus archivos)
curl -X DELETE http://localhost:8000/projects/{project_id}

# Guardar evaluacion de un proyecto
curl -X PUT http://localhost:8000/projects/{project_id}/ratings \
  -H "Content-Type: application/json" \
  -d '{
    "identifies_right_concerns": 8,
    "adherence_to_request": 9,
    "completeness_of_analysis": 7,
    "tech_stack_quality": 8,
    "document_clarity": 9,
    "risk_identification": 6,
    "actionability": 7,
    "comments": "Buen analisis general."
  }'

# Descargar un archivo adjunto
curl -O http://localhost:8000/projects/{project_id}/files/{file_id}
```

### 5.7. Validacion de input

La descripcion del proyecto debe tener al menos 10 caracteres. Si no:

```bash
curl -X POST http://localhost:8000/analyze/baseline \
  -F "description=short" \
  -F "provider=openai" \
  -F "model=gpt-4o-mini"
# -> HTTP 422 Unprocessable Entity
```

---

## 6. Ejecucion local (sin Docker)

Si prefieres ejecutar directamente en tu maquina sin Docker:

### 6.1. Instalar dependencias

```bash
# Instalar uv si no lo tienes
pip install uv

# Crear entorno virtual e instalar todo
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,frontend]"
```

### 6.2. Configurar .env

```bash
cp .env.example .env
# Editar .env con tu configuracion
# Si usas Ollama local, asegurate de que este corriendo y pon:
# OLLAMA_BASE_URL=http://localhost:11434
# Para MongoDB local:
# MONGODB_URL=mongodb://localhost:27017
```

### 6.3. Levantar MongoDB

```bash
docker run -d -p 27017:27017 -v mongodb_data:/data/db mongo:7
```

### 6.4. Levantar la API

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6.5. Levantar el frontend (en otra terminal)

```bash
streamlit run frontend/app.py --server.port 8501
```

---

## 7. Modelos disponibles

La seleccion de modelo se hace por peticion desde el frontend. Los modelos disponibles dependen de las API keys configuradas:

| Proveedor | Modelo | Tier | Vision | Coste (input/output por 1M tokens) |
|-----------|--------|------|--------|-------------------------------------|
| OpenAI | gpt-4o-mini | Economic | Si | $0.15 / $0.60 |
| OpenAI | gpt-5.2 | Performance | Si | $1.75 / $14.00 |
| Anthropic | claude-haiku-4-5 | Economic | Si | $1.00 / $5.00 |
| Anthropic | claude-sonnet-4-6 | Performance | Si | $3.00 / $15.00 |
| Ollama | llama3.2:3b (local) | Local | No | Gratis |

Para que un modelo aparezca en el frontend:
- **OpenAI**: necesita `OPENAI_API_KEY` en `.env`
- **Anthropic**: necesita `ANTHROPIC_API_KEY` en `.env`
- **Ollama**: necesita `ENVIRONMENT=local` y `--profile local`

---

## 8. Como funciona el flujo baseline

```
Usuario          Frontend (Streamlit)         API (FastAPI)            MongoDB         LangGraph / SingleAgent
  |                     |                          |                      |                      |
  |-- desc + modelo --->|                          |                      |                      |
  |-- archivos -------->|                          |                      |                      |
  |-- "Analyze" ------->|                          |                      |                      |
  |                     |-- POST /analyze/baseline |                      |                      |
  |                     |   (multipart form+files) |                      |                      |
  |                     |                          |-- procesa archivos   |                      |
  |                     |                          |-- crea proyecto ---->| (status=processing)  |
  |                     |                          |-- archivos→GridFS -->|                      |
  |                     |<-- {project_id, status} -|                      |                      |
  |                     |                          |-- asyncio.create_task ------------------>   |
  |<-- vista detalle ---|                          |                      |                      |
  |    (procesando...)  |                          |                      |                      |
  |                     |                          |                      |     (en background)   |
  |                     |                          |                      |     build prompt      |
  |                     |                          |                      |     call LLM          |
  |   (puede navegar    |-- GET /projects/{id} --->|                      |     extract markdown  |
  |    a otros proyectos)|<-- status=processing ---|                      |     extract metrics   |
  |                     |   (auto-refresh 3s)      |                      |                      |
  |                     |                          |                      |<---- complete_project |
  |                     |                          |                      | (status=completed,    |
  |                     |                          |                      |  markdown, metrics)   |
  |                     |-- GET /projects/{id} --->|                      |                      |
  |                     |<-- status=completed -----|                      |                      |
  |<-- muestra informe -|                          |                      |                      |
  |<-- historial actual.|                          |                      |                      |
```

1. El usuario escribe la descripcion, selecciona un modelo y (opcionalmente) adjunta archivos.
2. Streamlit envia un `POST /analyze/baseline` con multipart form data.
3. La API valida el modelo, procesa los archivos (extrae texto de PDFs, codifica imagenes en base64).
4. Crea el proyecto en MongoDB con `status: "processing"` y sube los archivos a GridFS.
5. Devuelve `{project_id, status: "processing"}` inmediatamente.
6. Lanza el analisis como tarea asincrona (`asyncio.create_task`):
   - Crea un grafo LangGraph con un solo nodo (`SingleAgent`), usando el modelo seleccionado.
   - El `SingleAgent` construye el prompt (sistema + usuario, con contenido multimodal si hay imagenes), llama al LLM y extrae el Markdown y las metricas.
   - Al terminar, actualiza el proyecto en MongoDB con `status: "completed"`, `markdown_content` y `metrics`. Si falla, lo marca con `status: "error"` y `error_message`.
7. Streamlit navega a la vista de detalle del proyecto y hace polling `GET /projects/{id}` cada 3 segundos, mostrando un cronometro y mensajes de progreso.
8. Cuando el status cambia a `"completed"`, renderiza el Markdown, las metricas, el boton de descarga y el formulario de evaluacion.

---

## 9. Persistencia con MongoDB

El sistema usa MongoDB para almacenar los proyectos y sus archivos adjuntos.

### 9.1. Estructura de datos

Cada proyecto se almacena como un documento en la coleccion `projects`:

```json
{
  "_id": ObjectId("..."),
  "created_at": ISODate("..."),
  "status": "processing | completed | error",
  "error_message": null,
  "description": "...",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "files": [
    {"file_id": "...", "name": "requirements.pdf", "size": 12345, "content_type": "application/pdf"}
  ],
  "markdown_content": "## 1. Resumen Ejecutivo\n...",
  "metrics": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "input_tokens": 1523,
    "output_tokens": 2847,
    "total_tokens": 4370,
    "execution_time_seconds": 12.453,
    "estimated_cost_usd": 0.001937
  },
  "ratings": null
}
```

- `status`: `"processing"` al crearse, `"completed"` tras el analisis, `"error"` si falla.
- `markdown_content` y `metrics` son `null` mientras `status` es `"processing"`.
- Los archivos binarios se almacenan en GridFS (colecciones `fs.files` y `fs.chunks`).

### 9.2. Consultar datos directamente

```bash
# Entrar al shell de MongoDB
docker compose exec mongodb mongosh tfg_architect

# Ver todos los proyectos
db.projects.find().pretty()

# Contar proyectos
db.projects.countDocuments()

# Ver archivos en GridFS
db.fs.files.find().pretty()
```

---

## 10. Endpoints de la API

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/health` | Estado de la API, entorno y proveedor LLM |
| GET | `/models` | Lista de modelos disponibles (filtrada por API keys y entorno) |
| POST | `/analyze/baseline` | Inicia un analisis (asincrono, devuelve project_id inmediatamente) |
| GET | `/projects` | Lista de proyectos (resumen para sidebar) |
| GET | `/projects/{id}` | Detalle completo de un proyecto |
| DELETE | `/projects/{id}` | Elimina un proyecto y sus archivos de GridFS |
| PUT | `/projects/{id}/ratings` | Guarda o actualiza la evaluacion de un proyecto |
| GET | `/projects/{id}/files/{file_id}` | Descarga un archivo adjunto desde GridFS |

Documentacion interactiva (Swagger): http://localhost:8000/docs

---

## 11. Observabilidad con LangSmith

LangSmith permite ver trazas detalladas de cada llamada al LLM (prompt completo, respuesta, tokens, tiempos).

### 11.1. Activar LangSmith

1. Crea una cuenta gratuita en https://smith.langchain.com
2. Genera una API key
3. Configura en `.env`:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...tu-clave...
LANGCHAIN_PROJECT=tfg-multiagent-architect
```

4. Reinicia los contenedores.

No hace falta cambiar codigo — LangChain envia automaticamente las trazas cuando estas variables estan activas.

### 11.2. Ver las trazas

Entra en https://smith.langchain.com, selecciona el proyecto y veras cada ejecucion con:
- El prompt completo enviado al LLM
- La respuesta completa
- Tokens de entrada/salida
- Latencia por paso
- Estructura del grafo LangGraph

---

## 12. Prompt del sistema

El prompt del monoagente (`src/llm/prompts.py`) instruye al LLM a generar un documento Markdown con 7 secciones:

1. **Resumen Ejecutivo** — Vision general, approach, trade-offs y riesgos criticos.
2. **Requisitos** — Funcionales (MUST/SHOULD/NICE) y no funcionales inferidos.
3. **Stack Tecnologico** — Recomendaciones con justificacion, pros, contras y alternativas.
4. **Arquitectura** — Patron arquitectonico, componentes, patrones de diseno, diagrama Mermaid e infraestructura.
5. **Riesgos y Mitigaciones** — Clasificados por severidad (ALTO/MEDIO/BAJO) con mitigacion concreta.
6. **Plan de Desarrollo** — Fases de desarrollo con duracion estimada y dependencias.
7. **Proximos Pasos** — 5-8 acciones concretas y asignables.

El mensaje de usuario incluye la descripcion del proyecto, los documentos adjuntos (texto extraido de archivos) y las imagenes codificadas en base64 para modelos con vision.

---

## 13. Troubleshooting

### La API no arranca

```bash
docker compose logs api
```

Causas comunes:
- MongoDB no ha terminado de arrancar.
- Error de sintaxis en el `.env`.

### Ollama no responde

```bash
# Comprobar que esta corriendo
docker compose --profile local ps

# Ver logs
docker compose --profile local logs ollama

# Comprobar que el modelo esta descargado
docker compose --profile local exec ollama ollama list
```

Si no aparece el modelo:

```bash
docker compose --profile local exec ollama ollama pull llama3.2:3b
```

### No aparecen modelos en el frontend

- Verifica que las API keys estan configuradas en `.env`
- Para modelos de OpenAI: `OPENAI_API_KEY` debe tener valor
- Para modelos de Anthropic: `ANTHROPIC_API_KEY` debe tener valor
- Para Ollama: `ENVIRONMENT=local` y levantado con `--profile local`
- Reinicia los contenedores despues de cambiar `.env`

### El frontend no conecta con la API

- Desde Docker: El frontend se conecta a `http://api:8000` (nombre del servicio en la red Docker). Si `API_BASE_URL` no esta configurado, usa `http://localhost:8000` que solo funciona fuera de Docker.
- Solucion dentro de Docker: Anade `API_BASE_URL=http://api:8000` al `.env`.
- Fuera de Docker: Deja `API_BASE_URL=http://localhost:8000` (valor por defecto).

### El historial no carga

- Verifica que MongoDB esta corriendo: `docker compose ps mongodb`
- Ver logs: `docker compose logs mongodb`
- Verifica la URL de conexion en `.env`: `MONGODB_URL=mongodb://mongodb:27017`

### Un proyecto se queda en "processing" indefinidamente

- Consulta los logs de la API: `docker compose logs -f api`
- El error se guarda en el campo `error_message` del proyecto. Consultalo con:
  ```bash
  curl http://localhost:8000/projects/{project_id}
  ```
- Si el status es `"error"`, el campo `error_message` contiene la causa.
- Si el contenedor de la API se reinicio durante un analisis, el proyecto quedara en `"processing"` para siempre. Eliminalo y vuelve a ejecutar el analisis.

---

## 14. Tabla de referencia rapida

| Accion | Comando |
|--------|---------|
| Levantar local | `docker compose --profile local up --build` |
| Levantar prod | `docker compose up --build` |
| Parar todo | `docker compose --profile local down` |
| Health check | `curl localhost:8000/health` |
| Modelos disponibles | `curl localhost:8000/models` |
| Listar proyectos | `curl localhost:8000/projects` |
| Abrir frontend | http://localhost:8501 |
| Descargar modelo Ollama | `docker compose --profile local exec ollama ollama pull llama3.2:3b` |
| Shell MongoDB | `docker compose exec mongodb mongosh tfg_architect` |
| Linting | `ruff check src/ tests/ frontend/` |
| Formatear codigo | `ruff format src/ tests/ frontend/` |
| Ver logs API | `docker compose logs -f api` |
| Ver logs MongoDB | `docker compose logs -f mongodb` |
| Ver logs Ollama | `docker compose --profile local logs -f ollama` |
| API docs (Swagger) | http://localhost:8000/docs |
