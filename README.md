# AI Software Architecture Agent

Sistema que genera informes de arquitectura de software a partir de la descripcion de un proyecto. Implementa dos modos de analisis (monoagente baseline y pipeline multiagente con 4 agentes especializados), soporta multiples proveedores LLM (OpenAI, Anthropic, Ollama), y produce informes descargables en Markdown o PDF con un chat post-generacion para profundizar en el contenido.

Proyecto de fin de grado — **Iker Alamo** · Universidad (2026).

---

## Indice

1. [Caracteristicas](#1-caracteristicas)
2. [Arquitectura del sistema](#2-arquitectura-del-sistema)
3. [Requisitos previos](#3-requisitos-previos)
4. [Instalacion con Docker](#4-instalacion-con-docker)
5. [Configuracion (.env)](#5-configuracion-env)
6. [Uso del sistema](#6-uso-del-sistema)
7. [Modelos LLM disponibles](#7-modelos-llm-disponibles)
8. [API REST](#8-api-rest)
9. [Ejecucion sin Docker](#9-ejecucion-sin-docker)
10. [Observabilidad con LangSmith](#10-observabilidad-con-langsmith)
11. [Troubleshooting](#11-troubleshooting)
12. [Referencia rapida](#12-referencia-rapida)
13. [Documentacion adicional](#13-documentacion-adicional)

---

## 1. Caracteristicas

- **Dos modos de analisis**:
  - **Monoagente (baseline)** — Una unica llamada LLM que produce el informe Markdown completo.
  - **Multiagente** — Pipeline de 4 agentes especializados (Planner, Requirements, Architecture Designer, Validator) orquestados con LangGraph, con fase de clarificacion obligatoria y feedback loop con hasta 2 revisiones automaticas.
- **Mezcla libre de proveedores**: Cada agente del multiagente puede usar un proveedor/modelo distinto (OpenAI, Anthropic, Ollama).
- **Entrada multimodal**: Descripcion en texto + archivos adjuntos (PDF, texto, codigo) + imagenes (solo modelos con vision).
- **Clarificacion interactiva**: En multiagente, el Planner siempre genera 3-5 preguntas de clarificacion antes de ejecutar el pipeline caro.
- **Informe final en Markdown**: 7 secciones (Resumen, Requisitos, Stack, Arquitectura con diagrama Mermaid, Riesgos, Plan, Proximos Pasos).
- **Descarga en .md o .pdf**: El PDF se genera on-the-fly con `fpdf2` (pure Python, sin dependencias del sistema).
- **Chat post-generacion**: Tras completarse el analisis, se puede conversar sobre el informe con el modelo LLM que elija el usuario. El historial se persiste en MongoDB.
- **Evaluacion estructurada**: Formulario de 7 criterios (0-10) para calificar la calidad del informe.
- **Historial completo**: Todos los proyectos se persisten en MongoDB con sus outputs intermedios, metricas por agente y archivos adjuntos en GridFS.
- **Metricas detalladas**: Tokens, tiempo de ejecucion y coste estimado por agente y agregados.

---

## 2. Arquitectura del sistema

```
+-----------------+        +------------------+       +-------------------+
|                 |        |                  |       |                   |
|   Streamlit     |<------>|    FastAPI       |<----->|     MongoDB       |
|   Frontend      |  HTTP  |    Backend       |       |  + GridFS         |
|   (port 8501)   |        |   (port 8000)    |       |  (port 27017)     |
|                 |        |                  |       |                   |
+-----------------+        +------------------+       +-------------------+
                                    |
                                    |  LangGraph (mono / multiagente)
                                    v
                            +---------------+
                            |   Proveedores |
                            |      LLM      |
                            |  OpenAI       |
                            |  Anthropic    |
                            |  Ollama local |
                            +---------------+
```

**Servicios orquestados por Docker Compose**:
- `api` (8000): FastAPI con hot-reload.
- `frontend` (8501): Streamlit.
- `mongodb` (27017): Persistencia de proyectos, chat y archivos en GridFS.
- `qdrant` (6333): Base vectorial (reservada para futuro RAG).
- `ollama` (11434): LLM local con soporte GPU (perfil `local`).

Para detalles de arquitectura interna, grafos LangGraph y estado compartido ver [docs/DOCUMENTACION_TECNICA_MULTIAGENTE.md](docs/DOCUMENTACION_TECNICA_MULTIAGENTE.md).

---

## 3. Requisitos previos

- **Docker** y **Docker Compose v2+** (metodo recomendado).
- **Python 3.11+** (solo si se quiere ejecutar sin Docker).
- **uv** (`pip install uv`, opcional para gestion de dependencias local).
- **GPU NVIDIA + drivers + nvidia-container-toolkit** (opcional, solo para acelerar Ollama local).
- Al menos una de:
  - API key de OpenAI (`OPENAI_API_KEY`),
  - API key de Anthropic (`ANTHROPIC_API_KEY`),
  - o `ENVIRONMENT=local` con el contenedor de Ollama (gratis pero mas lento y sin vision).

---

## 4. Instalacion con Docker

### 4.1 Clonar el repositorio

```bash
git clone <url-del-repo>
cd TFG_AI-Software-Architecture-Agent
```

### 4.2 Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con las API keys (ver seccion 5)
```

### 4.3 Levantar los servicios

**Entorno local (con Ollama, GPU opcional)**:

```bash
docker compose --profile local up --build
```

**Entorno sin Ollama (solo cloud)**:

```bash
docker compose up --build
```

### 4.4 (Solo la primera vez) Descargar el modelo de Ollama

```bash
docker compose --profile local exec ollama ollama pull llama3.2:3b
```

### 4.5 Acceder a la aplicacion

- **Frontend**: <http://localhost:8501>
- **API docs (Swagger)**: <http://localhost:8000/docs>
- **Health check**: <http://localhost:8000/health>

### 4.6 Parar los servicios

```bash
docker compose --profile local down       # deja datos intactos
docker compose --profile local down -v    # borra volumenes (datos de MongoDB y Ollama)
```

---

## 5. Configuracion (.env)

El proyecto usa un unico archivo `.env` (copia de `.env.example`) con las siguientes variables clave:

```env
# Entorno: local (con Ollama) | production (solo cloud)
ENVIRONMENT=local

# Proveedores LLM (rellena las que vayas a usar)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Modelos por defecto (los demas se definen en src/llm/models.py)
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_MODEL=claude-sonnet-4-6

# Ollama (local)
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b

# MongoDB
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DATABASE=tfg_architect

# Comunicacion frontend <-> API
API_BASE_URL=http://api:8000

# LangSmith (opcional, trazas de LLM)
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=tfg-multiagent-architect
```

**Que modelos aparecen en el frontend**:
- OpenAI -> requiere `OPENAI_API_KEY`.
- Anthropic -> requiere `ANTHROPIC_API_KEY`.
- Ollama -> requiere `ENVIRONMENT=local` y levantar con `--profile local`.

Tras modificar `.env` reinicia los contenedores: `docker compose --profile local restart api frontend`.

---

## 6. Uso del sistema

### 6.1 Acceso al frontend

Abre <http://localhost:8501>. La sidebar muestra:
- Estado de conexion con la API.
- Selector de modelo (monoagente) o selectores por agente (multiagente).
- Historial de proyectos previos con sus badges `[B]` (baseline) o `[M]` (multiagente).

### 6.2 Modo monoagente (baseline)

Rapido y barato. Una sola llamada al LLM genera el informe completo.

1. Pestaña **"Monoagente"** en la vista principal.
2. Escribe la descripcion del proyecto (minimo 10 caracteres).
3. (Opcional) Adjunta archivos: PDFs, texto, codigo, imagenes.
4. Selecciona modelo en la sidebar.
5. Pulsa **"Analizar"**.

El analisis corre en segundo plano. Puedes navegar a otros proyectos mientras termina.

### 6.3 Modo multiagente

Pipeline de 4 agentes con feedback loop. Mas caro y lento pero con mayor profundidad.

1. Pestaña **"Multiagente"**.
2. Escribe la descripcion del proyecto + (opcional) archivos.
3. Elige modelo:
   - **Toggle "Usar el mismo modelo para todos"** -> un solo selectbox para los 4 agentes.
   - **Sin toggle** -> 4 selectboxes independientes (puedes mezclar proveedores, p. ej. Planner con OpenAI + Designer con Anthropic).
4. Pulsa **"Analizar"**.

### 6.4 Clarificacion (siempre obligatoria)

Tras la fase Planner, el proyecto queda en estado `waiting_clarification`. El frontend muestra entre 3 y 5 preguntas con opciones sugeridas.

- Selecciona una opcion para cada pregunta mediante radio buttons.
- Si ninguna encaja, elige **"Otro (escribir abajo)"** y escribe tu respuesta libre.
- Pulsa **"Continuar analisis"** para disparar la segunda fase del pipeline (Requirements -> Designer -> Validator).

El Validator puede solicitar hasta 2 revisiones automaticas a Requirements o Designer si detecta inconsistencias. A la tercera vuelta se fuerza la consolidacion del informe final.

### 6.5 Historial de proyectos

El sidebar muestra todos los analisis previos con indicadores:
- `...` -> en proceso
- `?` -> esperando clarificacion
- `ERR` -> error
- `*` -> proyecto evaluado
- (sin marca) -> completado sin evaluar

Click en una entrada para ver su detalle. Boton **"x"** para borrarla (elimina documento + archivos GridFS + chat).

### 6.6 Evaluacion del informe

En la vista de detalle (proyecto completado) hay un formulario de 7 criterios (0-10):

1. Identifica las preocupaciones correctas
2. Se ajusta a lo pedido
3. Completitud del analisis tecnico
4. Calidad de la recomendacion tecnologica
5. Claridad y estructura del documento
6. Identificacion de riesgos
7. Plan de desarrollo accionable

Mas un campo libre de comentarios. Pulsa **"Guardar evaluacion"** para persistir.

### 6.7 Descarga del informe (.md / .pdf)

En la vista de detalle hay dos botones:
- **Descargar .md** -> Markdown directo.
- **Descargar .pdf** -> PDF generado on-the-fly con `fpdf2`. Convierte headings, listas, tablas y bloques de codigo. Los diagramas Mermaid no se renderizan como grafico en PDF — se incluyen como fuente plana con una etiqueta "Diagrama (fuente Mermaid):".

### 6.8 Chat sobre el informe

Tras el formulario de evaluacion aparece un chat conversacional:

1. Selector inline de proveedor/modelo (por defecto usa el mismo modelo del analisis).
2. Caja de entrada `"Pregunta algo sobre el informe..."`.
3. El historial de la conversacion se muestra encima en burbujas y se persiste en MongoDB (`chat_history`).
4. Cada respuesta del asistente guarda tambien sus metricas (tokens, tiempo, coste).

El chat no es un agente del pipeline — es una llamada directa al LLM con el informe inyectado en el system prompt. Puedes cambiar de modelo entre mensajes sin perder el historial.

---

## 7. Modelos LLM disponibles

| Proveedor | Modelo | Tier | Vision | Coste (input/output por 1M tokens) |
|-----------|--------|------|--------|-------------------------------------|
| OpenAI | gpt-4o-mini | Economic | Si | $0.15 / $0.60 |
| OpenAI | gpt-5.2 | Performance | Si | $1.75 / $14.00 |
| Anthropic | claude-haiku-4-5 | Economic | Si | $1.00 / $5.00 |
| Anthropic | claude-sonnet-4-6 | Performance | Si | $3.00 / $15.00 |
| Ollama | configurable en .env | Local | No | Gratis |

**Recomendacion practica**: Para el multiagente, combinar un modelo barato (gpt-4o-mini) en Planner/Designer con uno mas capaz (Sonnet) en Requirements/Validator da buena relacion coste/calidad.

El catalogo y el filtrado de modelos vive en [src/llm/models.py](src/llm/models.py) y los precios en [src/utils/cost.py](src/utils/cost.py).

---

## 8. API REST

Documentacion interactiva: <http://localhost:8000/docs>

### 8.1 Endpoints principales

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/health` | Estado del servicio, entorno, proveedor LLM |
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

### 8.2 Ejemplo: lanzar un analisis multiagente por curl

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

Respuesta:

```json
{"project_id": "683d...", "status": "processing"}
```

### 8.3 Ejemplo: responder clarificacion

```bash
curl -X POST http://localhost:8000/projects/{project_id}/clarification \
  -H "Content-Type: application/json" \
  -d '{
    "answers": {
      "Que base de datos prefieres?": "PostgreSQL",
      "Que volumen de usuarios esperas?": "~1000 concurrentes"
    }
  }'
```

### 8.4 Ejemplo: descargar PDF

```bash
curl -o informe.pdf http://localhost:8000/projects/{project_id}/download/pdf
```

### 8.5 Ejemplo: chatear sobre el informe

```bash
curl -X POST http://localhost:8000/projects/{project_id}/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Por que recomendais Postgres en vez de MongoDB?",
    "provider": "openai",
    "model": "gpt-4o-mini"
  }'
```

---

## 9. Ejecucion sin Docker

### 9.1 Dependencias

```bash
pip install uv
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,frontend]"
```

### 9.2 Levantar MongoDB y Qdrant manualmente

```bash
docker run -d -p 27017:27017 -v mongodb_data:/data/db mongo:7
docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant:v1.13.2
```

### 9.3 Ajustar `.env`

```env
OLLAMA_BASE_URL=http://localhost:11434
MONGODB_URL=mongodb://localhost:27017
API_BASE_URL=http://localhost:8000
```

### 9.4 Arrancar la API

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 9.5 Arrancar el frontend (otra terminal)

```bash
streamlit run frontend/app.py --server.port 8501
```

---

## 10. Observabilidad con LangSmith

LangSmith permite inspeccionar cada llamada al LLM (prompt, respuesta, tokens, latencia) y la estructura del grafo LangGraph.

1. Crea una cuenta en <https://smith.langchain.com>.
2. Genera una API key.
3. Configura en `.env`:

   ```env
   LANGCHAIN_TRACING_V2=true
   LANGSMITH_API_KEY=lsv2_pt_...
   LANGSMITH_PROJECT=tfg-multiagent-architect
   ```

4. Reinicia los contenedores.

LangChain envia las trazas automaticamente — no hace falta tocar codigo.

---

## 11. Troubleshooting

### No aparecen modelos en el frontend

- Verifica que las API keys estan en `.env` con valor no vacio.
- Para Ollama: `ENVIRONMENT=local` + `--profile local` + modelo descargado (`ollama pull`).
- Reinicia `api` y `frontend` tras cambiar `.env`.

### El frontend no conecta con la API

Dentro de Docker, el frontend debe apuntar al servicio por su nombre de red:

```env
API_BASE_URL=http://api:8000
```

Fuera de Docker: `API_BASE_URL=http://localhost:8000`.

### El historial no carga

- Revisa `docker compose ps mongodb` y `docker compose logs mongodb`.
- Confirma `MONGODB_URL=mongodb://mongodb:27017` (dentro de Docker).

### Un proyecto se queda en "processing" indefinidamente

- Revisa `docker compose logs -f api`.
- Consulta `curl http://localhost:8000/projects/{id}` — si `status=="error"` el campo `error_message` da la causa.
- Si la API se reinicio durante un analisis, el proyecto queda colgado. Elimina y relanza.

### El PDF sale con caracteres raros

El generador reemplaza la mayoria de caracteres Unicode no soportados por Helvetica/Courier por equivalentes ASCII (comillas tipograficas, guiones em/en, flechas, simbolos matematicos, etc.). Si aparece algun caracter exotico no cubierto, anadir el mapeo en `_sanitize()` de [src/utils/pdf.py](src/utils/pdf.py).

### El chat responde lento o falla

- Si usas Ollama, las respuestas son mas lentas que con APIs cloud.
- Comprueba las API keys y la disponibilidad del modelo seleccionado.
- El endpoint `/chat` devuelve 404 si el proyecto no esta en estado `completed`.

### Ollama: "model not found"

```bash
docker compose --profile local exec ollama ollama list
docker compose --profile local exec ollama ollama pull <modelo>
```

---

## 12. Referencia rapida

| Accion | Comando |
|--------|---------|
| Levantar local | `docker compose --profile local up --build` |
| Levantar prod | `docker compose up --build` |
| Parar todo | `docker compose --profile local down` |
| Reiniciar api+frontend | `docker compose restart api frontend` |
| Ver logs API | `docker compose logs -f api` |
| Ver logs Ollama | `docker compose --profile local logs -f ollama` |
| Health check | `curl localhost:8000/health` |
| Swagger UI | <http://localhost:8000/docs> |
| Frontend | <http://localhost:8501> |
| Shell MongoDB | `docker compose exec mongodb mongosh tfg_architect` |
| Descargar modelo Ollama | `docker compose --profile local exec ollama ollama pull llama3.2:3b` |
| Linting | `ruff check src/ tests/ frontend/` |
| Formatear | `ruff format src/ tests/ frontend/` |

---

## 13. Documentacion adicional

- **[docs/DOCUMENTACION_TECNICA_MULTIAGENTE.md](docs/DOCUMENTACION_TECNICA_MULTIAGENTE.md)** — Arquitectura interna del sistema multiagente: grafos LangGraph, estado compartido, prompts, persistencia y decisiones de diseno.
- **[docs/MANUAL_USO_MONOAGENTE.md](docs/MANUAL_USO_MONOAGENTE.md)** — Manual detallado del modo monoagente (Fase 1).
- **[docs/diagrama_multiagente.drawio.xml](docs/diagrama_multiagente.drawio.xml)** — Diagrama del flujo multiagente (abrir con <https://app.diagrams.net>).
- **[docs/PUNTO_DE_PARTIDA.md](docs/PUNTO_DE_PARTIDA.md)** — Vision y objetivos iniciales del proyecto.

---

## Licencia

Ver [LICENSE](LICENSE).
