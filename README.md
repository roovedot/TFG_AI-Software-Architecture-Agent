# AI Software Architecture Agent

Sistema multiagente que genera propuestas de arquitectura de software a partir de la descripcion de un proyecto. Implementa dos modos (monoagente baseline y pipeline multiagente con 4 agentes especializados orquestados con LangGraph), soporta OpenAI / Anthropic / Ollama, y produce informes descargables en Markdown o PDF con un chat post-generacion para profundizar en el contenido.

Proyecto de Fin de Grado (Ingenieria Informatica) — **Iker Alamo** · Universidad Europea de Madrid (2026).

---

## Indice

1. [Caracteristicas](#1-caracteristicas)
2. [Arquitectura del sistema](#2-arquitectura-del-sistema)
3. [Despliegue](#3-despliegue)
4. [Requisitos previos](#4-requisitos-previos)
5. [Instalacion con Docker](#5-instalacion-con-docker)
6. [Configuracion (.env)](#6-configuracion-env)
7. [Uso del sistema](#7-uso-del-sistema)
8. [Modelos LLM disponibles](#8-modelos-llm-disponibles)
9. [API REST](#9-api-rest)
10. [Ejecucion sin Docker](#10-ejecucion-sin-docker)
11. [Observabilidad con LangSmith](#11-observabilidad-con-langsmith)
12. [Troubleshooting](#12-troubleshooting)
13. [Referencia rapida](#13-referencia-rapida)
14. [Documentacion adicional](#14-documentacion-adicional)

---

## 1. Caracteristicas

- **Dos modos de analisis**:
  - **Monoagente (baseline)** — Una unica llamada LLM que produce el informe Markdown completo.
  - **Multiagente** — Pipeline de 4 agentes especializados (Planner, Requirements & Tech-Stack, Architecture Designer, Validator & Aggregator) orquestados con LangGraph, con fase de clarificacion obligatoria y feedback loop con hasta 2 revisiones automaticas.
- **Mezcla libre de proveedores**: Cada agente del multiagente puede usar un proveedor/modelo distinto (OpenAI, Anthropic, Ollama).
- **Entrada multimodal**: Descripcion en texto + archivos adjuntos (PDF, texto, codigo) + imagenes (solo modelos con vision).
- **Clarificacion interactiva**: En multiagente, el Planner siempre genera 3-5 preguntas con opciones sugeridas antes de ejecutar el pipeline caro.
- **Informe final en Markdown** con 7 secciones: Resumen, Requisitos, Stack, Arquitectura con diagrama Mermaid, Riesgos, Plan, Proximos Pasos.
- **Descarga en .md o .pdf**: El PDF se genera on-the-fly con `fpdf2` (pure Python, sin dependencias del sistema).
- **Chat post-generacion**: Tras completarse el analisis, se puede conversar sobre el informe con el modelo LLM que elija el usuario. El historial se persiste en MongoDB.
- **Evaluacion estructurada**: Formulario de 7 criterios (0-10) para calificar la calidad del informe.
- **Historial completo** en MongoDB con outputs intermedios, metricas por agente y archivos adjuntos en GridFS.
- **Metricas detalladas**: Tokens, tiempo de ejecucion y coste estimado por agente y agregados.

---

## 2. Arquitectura del sistema

![Flujo del sistema multiagente](docs/img/Diagrama%20de%20Flujo%20TFG.drawio.png)

El sistema sigue un pipeline LangGraph con dos fases separadas por una pausa obligatoria de clarificacion:

**Fase 1 — Planner:**
1. El usuario envia descripcion + archivos desde el **Streamlit Frontend** via `POST /analyze/multiagent`.
2. **FastAPI Backend** valida modelos, crea el proyecto en MongoDB y lanza la fase Planner como background task (`asyncio.create_task`).
3. El **Planner Agent** analiza la descripcion y genera un `analysis_plan` + **siempre 3-5 preguntas de clarificacion**. El proyecto queda en estado `waiting_clarification` y el frontend detecta la pausa.
4. El usuario responde (radio buttons con opciones o texto libre). El frontend envia `POST /projects/{id}/clarification`.

**Fase 2 — Pipeline Graph (LangGraph con feedback loop):**
5. **Requirements & Tech-Stack Agent** — genera requisitos funcionales/no funcionales y recomendacion de stack (output JSON).
6. **Architecture Designer Agent** — define patron, componentes, diagrama Mermaid, infraestructura y riesgos (output JSON).
7. **Validator & Aggregator Agent** — valida coherencia y consolida el Markdown final. Si detecta inconsistencias, devuelve `target=requirements` o `target=designer` (max 2 revisiones). A la tercera vuelta se fuerza la consolidacion.
8. El **Informe Final** (Markdown, 7 secciones) se guarda en MongoDB junto con metricas por agente y outputs intermedios.

**Post-generacion** (disponible cuando `status == completed`):
- `GET /projects/{id}/download/pdf` — descarga en PDF.
- `POST /projects/{id}/chat` — chat sobre el informe con cualquier modelo LLM.
- Formulario de evaluacion (7 criterios, 0-10).

**Servicios Docker Compose**:

| Servicio | Puerto | Rol |
|---|---|---|
| `frontend` | 8501 | Streamlit |
| `api` | 8000 | FastAPI + LangGraph |
| `mongodb` | 27017 | Proyectos, outputs, chat, GridFS |
| `ollama` | 11434 | LLM local con GPU (perfil `local`) |

Para detalles de grafos LangGraph, estado compartido y prompts ver [docs/DOCUMENTACION_TECNICA_MULTIAGENTE.md](docs/DOCUMENTACION_TECNICA_MULTIAGENTE.md).

---

## 3. Despliegue

### 3.1 Entorno de desarrollo (local)

Todos los contenedores corren en la maquina del desarrollador bajo **Docker Compose** con el perfil `local`. Los puertos se exponen directamente a `localhost` sin reverse proxy:

- `localhost:8501` — Streamlit frontend
- `localhost:8000` — FastAPI API (y Swagger en `/docs`)
- `localhost:27017` — MongoDB
- `localhost:11434` — Ollama con GPU NVIDIA

El developer accede al frontend normalmente por el navegador y puede acceder directamente a Swagger (`http://localhost:8000/docs`) para pruebas de API. Ollama se levanta solo con `--profile local`.

![Diagrama de despliegue dev](docs/img/Arquitectura%20Dev%20TFG.drawio.png)

### 3.2 Entorno de produccion

Despliegue sobre servidor con **CloudPanel + Nginx** como reverse proxy. Solo el frontend queda expuesto publicamente via el dominio (`architectureagent.dominio.com`); la API y MongoDB se vinculan unicamente a `127.0.0.1`. Ollama no se despliega en produccion — se usan exclusivamente OpenAI / Anthropic.

- `127.0.0.1:8501` — Streamlit (proxied por Nginx)
- `127.0.0.1:8000` — FastAPI (interno)
- `127.0.0.1:27017` — MongoDB (interno, acceso via SSH tunnel para administracion)

![Diagrama de despliegue prod](docs/img/Arquitectura%20Prod%20TFG.drawio.png)

---

## 4. Requisitos previos

- **Docker** y **Docker Compose v2+** (metodo recomendado).
- **Python 3.11+** (solo para ejecucion sin Docker).
- **uv** (`pip install uv`, opcional para gestion de dependencias local).
- **GPU NVIDIA + drivers + nvidia-container-toolkit** (opcional, solo para acelerar Ollama local).
- Al menos una de:
  - API key de OpenAI (`OPENAI_API_KEY`),
  - API key de Anthropic (`ANTHROPIC_API_KEY`),
  - o `ENVIRONMENT=local` con el contenedor de Ollama (gratis pero mas lento y sin vision).

---

## 5. Instalacion con Docker

### 5.1 Clonar el repositorio

```bash
git clone <url-del-repo>
cd TFG_AI-Software-Architecture-Agent
```

### 5.2 Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con las API keys (ver seccion 6)
```

### 5.3 Levantar los servicios

**Entorno local (con Ollama + GPU)**:

```bash
sudo docker compose --profile local up -d
```

**Entorno produccion (sin Ollama, cambiar `ENVIRONMENT=production` en .env)**:

```bash
sudo docker compose up -d
```

### 5.4 (Solo la primera vez) Descargar el modelo de Ollama

Si el modelo oficial no esta disponible por Cloudflare, usar el mirror de HuggingFace:

```bash
# Desde HuggingFace GGUF
sudo docker compose --profile local exec ollama \
  ollama pull hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M

# Crear alias para que quede como llama3.2:3b
sudo docker compose --profile local exec ollama \
  ollama cp "hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M" llama3.2:3b

# Probar interactivamente
sudo docker compose --profile local exec ollama ollama run llama3.2:3b "hola"
```

### 5.5 Acceder a la aplicacion

- **Frontend**: <http://localhost:8501>
- **API docs (Swagger)**: <http://localhost:8000/docs>
- **Health check**: <http://localhost:8000/health>

### 5.6 Parar los servicios

```bash
sudo docker compose --profile local down      # deja datos intactos
sudo docker compose --profile local down -v   # borra volumenes (MongoDB + Ollama)
```

---

## 6. Configuracion (.env)

El proyecto usa un unico archivo `.env` (copia de `.env.example`). Variables clave:

```env
# Entorno: local (con Ollama) | production (solo cloud)
ENVIRONMENT=local

# LLM por defecto (el frontend permite sobreescribir por peticion)
LLM_PROVIDER=ollama

# OpenAI
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# Anthropic
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6

# Ollama (modelo local, solo con --profile local)
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b

# MongoDB
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DATABASE=tfg_architect

# API
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true
LOG_LEVEL=debug

# Frontend -> API (dentro de Docker)
API_BASE_URL=http://api:8000

# LangSmith (opcional, trazas LLM)
LANGCHAIN_TRACING_V2=true
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
LANGCHAIN_API_KEY=
LANGSMITH_API_KEY=
LANGCHAIN_PROJECT=TFG
LANGSMITH_PROJECT=TFG
```

**Que modelos aparecen en el frontend**:

- OpenAI -> requiere `OPENAI_API_KEY` no vacia.
- Anthropic -> requiere `ANTHROPIC_API_KEY` no vacia.
- Ollama -> requiere `ENVIRONMENT=local` y levantar con `--profile local`.

Tras modificar `.env` reinicia los contenedores: `sudo docker compose --profile local restart api frontend`.

---

## 7. Uso del sistema

### 7.1 Acceso al frontend

Abre <http://localhost:8501>. La sidebar muestra:

- Estado de conexion con la API.
- Selector de modelo (monoagente) o selectores por agente (multiagente).
- Historial de proyectos previos con badges `[B]` (baseline) o `[M]` (multiagente).

### 7.2 Modo monoagente (baseline)

Rapido y barato. Una sola llamada al LLM genera el informe completo.

1. Pestaña **"Monoagente"**.
2. Escribe la descripcion del proyecto (minimo 10 caracteres).
3. (Opcional) Adjunta archivos: PDFs, texto, codigo, imagenes.
4. Selecciona modelo en la sidebar.
5. Pulsa **"Analizar"**. El analisis corre en segundo plano.

### 7.3 Modo multiagente

Pipeline de 4 agentes con feedback loop. Mas caro y lento pero con mayor profundidad.

1. Pestaña **"Multiagente"**.
2. Escribe la descripcion del proyecto + (opcional) archivos.
3. Elige modelo:
   - **Toggle "Usar el mismo modelo para todos"** -> un solo selectbox para los 4 agentes.
   - **Sin toggle** -> 4 selectboxes independientes (p. ej. Planner con OpenAI + Designer con Anthropic).
4. Pulsa **"Analizar"**.

### 7.4 Clarificacion (siempre obligatoria)

Tras la fase Planner, el proyecto queda en `waiting_clarification`. El frontend muestra 3-5 preguntas con opciones sugeridas.

- Selecciona una opcion por pregunta (radio buttons).
- Si ninguna encaja, elige **"Otro (escribir abajo)"** y escribe tu respuesta libre.
- Pulsa **"Continuar analisis"** para disparar la segunda fase (Requirements -> Designer -> Validator).

El Validator puede solicitar hasta 2 revisiones automaticas si detecta inconsistencias. A la tercera vuelta se fuerza la consolidacion del informe final.

### 7.5 Historial de proyectos

El sidebar muestra todos los analisis previos con indicadores:

- `...` -> en proceso
- `?` -> esperando clarificacion
- `ERR` -> error
- `*` -> proyecto evaluado
- (sin marca) -> completado sin evaluar

Click para ver el detalle. Boton **"x"** para borrar (elimina documento + archivos GridFS + chat).

### 7.6 Evaluacion del informe

En la vista de detalle (proyecto completado) hay un formulario de 7 criterios (0-10):

1. Identifica las preocupaciones correctas
2. Se ajusta a lo pedido
3. Completitud del analisis tecnico
4. Calidad de la recomendacion tecnologica
5. Claridad y estructura del documento
6. Identificacion de riesgos
7. Plan de desarrollo accionable

Mas un campo libre de comentarios. Pulsa **"Guardar evaluacion"** para persistir.

### 7.7 Descarga del informe (.md / .pdf)

En la vista de detalle hay dos botones:

- **Descargar .md** -> Markdown directo.
- **Descargar .pdf** -> PDF generado on-the-fly con `fpdf2`. Convierte headings, listas, tablas y bloques de codigo. Los diagramas Mermaid no se renderizan como grafico — se incluyen como fuente plana con la etiqueta "Diagrama (fuente Mermaid):".

### 7.8 Chat sobre el informe

Tras el formulario de evaluacion aparece un chat conversacional:

1. Selector inline de proveedor/modelo (por defecto usa el mismo del analisis).
2. Caja de entrada `"Pregunta algo sobre el informe..."`.
3. El historial se muestra encima en burbujas y se persiste en MongoDB (`chat_history`).
4. Cada respuesta del asistente guarda sus metricas (tokens, tiempo, coste).

El chat no es un agente del pipeline — es una llamada directa al LLM con el informe inyectado en el system prompt. Puedes cambiar de modelo entre mensajes sin perder el historial.

---

## 8. Modelos LLM disponibles

| Proveedor | Modelo | Tier | Vision | Coste (input/output por 1M tokens) |
|---|---|---|---|---|
| OpenAI | gpt-4o-mini | Economic | Si | $0.15 / $0.60 |
| OpenAI | gpt-5.2 | Performance | Si | $1.75 / $14.00 |
| Anthropic | claude-haiku-4-5 | Economic | Si | $1.00 / $5.00 |
| Anthropic | claude-sonnet-4-6 | Performance | Si | $3.00 / $15.00 |
| Ollama | configurable en .env | Local | No | Gratis |

**Recomendacion practica**: Para el multiagente, combinar un modelo barato (gpt-4o-mini) en Planner/Designer con uno mas capaz (Sonnet) en Requirements/Validator da buena relacion coste/calidad.

El catalogo y filtrado vive en [src/llm/models.py](src/llm/models.py) y los precios en [src/utils/cost.py](src/utils/cost.py).

---

## 9. API REST

Documentacion interactiva: <http://localhost:8000/docs>

### 9.1 Endpoints

| Metodo | Ruta | Descripcion |
|---|---|---|
| GET | `/health` | Estado del servicio |
| GET | `/models` | Modelos disponibles (filtrados por API keys y entorno) |
| POST | `/analyze/baseline` | Iniciar analisis monoagente (FormData) |
| POST | `/analyze/multiagent` | Iniciar analisis multiagente (FormData con 8 campos de modelo) |
| POST | `/projects/{id}/clarification` | Enviar respuestas de clarificacion |
| GET | `/projects` | Listar proyectos (historial) |
| GET | `/projects/{id}` | Detalle completo |
| DELETE | `/projects/{id}` | Eliminar proyecto + archivos + chat |
| PUT | `/projects/{id}/ratings` | Guardar evaluacion (7 criterios) |
| GET | `/projects/{id}/files/{fid}` | Descargar archivo adjunto desde GridFS |
| GET | `/projects/{id}/download/pdf` | Descargar informe como PDF |
| POST | `/projects/{id}/chat` | Enviar mensaje al chat post-generacion |

### 9.2 Ejemplos basicos (curl)

```bash
# Health check
curl localhost:8000/health

# Listar modelos disponibles
curl localhost:8000/models

# Listar proyectos
curl localhost:8000/projects

# Detalle de un proyecto
curl localhost:8000/projects/{PROJECT_ID}

# Eliminar un proyecto
curl -X DELETE localhost:8000/projects/{PROJECT_ID}
```

### 9.3 Lanzar un analisis multiagente

```bash
curl -X POST http://localhost:8000/analyze/multiagent \
  -F "description=Plataforma de comercio electronico para tienda local. Equipo de 3 developers, 6 meses, budget limitado." \
  -F "planner_provider=openai" \
  -F "planner_model=gpt-4o-mini" \
  -F "requirements_provider=anthropic" \
  -F "requirements_model=claude-sonnet-4-6" \
  -F "designer_provider=openai" \
  -F "designer_model=gpt-4o-mini" \
  -F "validator_provider=anthropic" \
  -F "validator_model=claude-sonnet-4-6"
```

### 9.4 Responder clarificacion

```bash
curl -X POST http://localhost:8000/projects/{PROJECT_ID}/clarification \
  -H "Content-Type: application/json" \
  -d '{
    "answers": {
      "Que base de datos prefieres?": "PostgreSQL",
      "Que volumen de usuarios esperas?": "~1000 concurrentes"
    }
  }'
```

### 9.5 Descargar PDF y chatear

```bash
# PDF
curl -o informe.pdf http://localhost:8000/projects/{PROJECT_ID}/download/pdf

# Chat
curl -X POST http://localhost:8000/projects/{PROJECT_ID}/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Por que recomendais Postgres en vez de MongoDB?",
    "provider": "openai",
    "model": "gpt-4o-mini"
  }'
```

---

## 10. Ejecucion sin Docker

### 10.1 Dependencias

```bash
pip install uv
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,frontend]"
```

### 10.2 Levantar MongoDB manualmente

```bash
docker run -d -p 27017:27017 -v mongodb_data:/data/db mongo:7
```

### 10.3 Ajustar `.env`

```env
OLLAMA_BASE_URL=http://localhost:11434
MONGODB_URL=mongodb://localhost:27017
API_BASE_URL=http://localhost:8000
```

### 10.4 Arrancar la API

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 10.5 Arrancar el frontend (otra terminal)

```bash
streamlit run frontend/app.py --server.port 8501
```

---

## 11. Observabilidad con LangSmith

LangSmith permite inspeccionar cada llamada al LLM (prompt, respuesta, tokens, latencia) y la estructura del grafo LangGraph.

1. Crea una cuenta en <https://smith.langchain.com>.
2. Genera una API key.
3. Configura en `.env`:

   ```env
   LANGCHAIN_TRACING_V2=true
   LANGSMITH_TRACING=true
   LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
   LANGCHAIN_API_KEY=lsv2_pt_...
   LANGSMITH_API_KEY=lsv2_pt_...
   LANGCHAIN_PROJECT=TFG
   LANGSMITH_PROJECT=TFG
   ```

4. Reinicia los contenedores.

LangChain envia las trazas automaticamente — no hace falta tocar codigo.

---

## 12. Troubleshooting

### No aparecen modelos en el frontend

- Verifica que las API keys estan en `.env` con valor no vacio.
- Para Ollama: `ENVIRONMENT=local` + `--profile local` + modelo descargado (`ollama pull`).
- Reinicia `api` y `frontend` tras cambiar `.env`.

### El frontend no conecta con la API

Dentro de Docker el frontend debe apuntar al servicio por su nombre de red:

```env
API_BASE_URL=http://api:8000
```

Fuera de Docker: `API_BASE_URL=http://localhost:8000`.

### El historial no carga

- Revisa `sudo docker compose ps mongodb` y `sudo docker compose logs mongodb`.
- Confirma `MONGODB_URL=mongodb://mongodb:27017` (dentro de Docker).
- Shell directo: `sudo docker compose exec mongodb mongosh tfg_architect`.

### Un proyecto se queda en "processing" indefinidamente

- `sudo docker compose logs -f api`.
- `curl http://localhost:8000/projects/{id}` — si `status=="error"` el campo `error_message` da la causa.
- Si la API se reinicio durante un analisis, el proyecto queda colgado. Elimina y relanza.

### El PDF sale con caracteres raros

El generador reemplaza la mayoria de caracteres Unicode no soportados por Helvetica/Courier por equivalentes ASCII (comillas tipograficas, guiones em/en, flechas, simbolos matematicos, etc.). Si aparece algun caracter exotico no cubierto, anadir el mapeo en `_sanitize()` de [src/utils/pdf.py](src/utils/pdf.py).

### El chat responde lento o falla

- Si usas Ollama, las respuestas son mas lentas que con APIs cloud.
- Comprueba las API keys y la disponibilidad del modelo seleccionado.
- El endpoint `/chat` devuelve 404 si el proyecto no esta en estado `completed`.

### Ollama: "model not found"

```bash
sudo docker compose --profile local exec ollama ollama list
sudo docker compose --profile local exec ollama \
  ollama pull hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M
```

---

## 13. Referencia rapida

| Accion | Comando |
|---|---|
| Levantar local | `sudo docker compose --profile local up -d` |
| Levantar prod | `sudo docker compose up -d` |
| Parar local | `sudo docker compose --profile local down` |
| Parar prod | `sudo docker compose down` |
| Logs local | `sudo docker compose --profile local logs -f` |
| Logs prod | `sudo docker compose logs -f` |
| Logs de un servicio | `sudo docker compose logs -f api` (o `ollama` / `mongodb`) |
| Reiniciar api+frontend | `sudo docker compose restart api frontend` |
| Health check | `curl localhost:8000/health` |
| Swagger UI | <http://localhost:8000/docs> |
| Frontend | <http://localhost:8501> |
| Shell MongoDB | `sudo docker compose exec mongodb mongosh tfg_architect` |
| Ver proyectos en Mongo | `sudo docker compose exec mongodb mongosh tfg_architect --eval "db.projects.find().pretty()"` |
| Ver archivos GridFS | `sudo docker compose exec mongodb mongosh tfg_architect --eval "db.fs.files.find().pretty()"` |
| Modelos Ollama | `sudo docker compose --profile local exec ollama ollama list` |
| Linting | `ruff check src/ tests/ frontend/` |
| Formatear | `ruff format src/ tests/ frontend/` |

---

## 14. Documentacion adicional

- **[docs/DOCUMENTACION_TECNICA_MULTIAGENTE.md](docs/DOCUMENTACION_TECNICA_MULTIAGENTE.md)** — Arquitectura interna del sistema multiagente: grafos LangGraph, estado compartido, prompts, persistencia y decisiones de diseno.
- **[docs/MANUAL_USO_MONOAGENTE.md](docs/MANUAL_USO_MONOAGENTE.md)** — Manual detallado del modo monoagente (Fase 1).
- **[docs/PUNTO_DE_PARTIDA.md](docs/PUNTO_DE_PARTIDA.md)** — Vision y objetivos iniciales del proyecto.
- **[Cheatsheet_comandos.txt](Cheatsheet_comandos.txt)** — Chuleta de comandos de uso diario (Docker, Ollama, MongoDB, API).

---

## Licencia

Ver [LICENSE](LICENSE).
