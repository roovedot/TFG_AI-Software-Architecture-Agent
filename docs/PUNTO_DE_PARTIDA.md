# Contexto del Proyecto TFG: Sistema Multi-Agente para Arquitectura de Software

## 🎯 Objetivo del Proyecto

Desarrollar un sistema multi-agente basado en LLMs que automatice el diseño de arquitectura técnica y planificación de proyectos de software. El sistema debe analizar descripciones de proyectos y generar propuestas completas de:

- Arquitectura técnica (justificada y documentada)
- Stack tecnológico recomendado (frameworks, librerías, bases de datos)
- Diseño de infraestructura (Docker, servicios, patrones)
- Plan de desarrollo (fases, tareas, estimaciones)
- Análisis de riesgos y alternativas

## 📋 Caso de Uso Principal

**Input:** Documento o descripción textual de un proyecto software (requisitos, alcance, recursos disponibles)

**Output:** Informe estructurado (JSON + Markdown) con:
- Propuesta de arquitectura técnica
- Recomendaciones de tecnologías con justificación
- Diseño de infraestructura
- Plan de desarrollo detallado
- Análisis de viabilidad y riesgos

## 🏗️ Arquitectura del Sistema

### Enfoque Multi-Agente

El sistema implementa **4 agentes especializados** que colaboran secuencialmente:

```
Usuario (input de proyecto)
    ↓
[1] Planner Agent
    - Analiza input
    - Crea plan de análisis
    - Coordina flujo
    ↓
[2] Requirements & Tech Stack Agent
    - Extrae requisitos funcionales/no funcionales
    - Clasifica por prioridad
    - Recomienda stack tecnológico
    - Justifica decisiones (pros/contras)
    ↓
[3] Architecture Designer Agent
    - Diseña arquitectura (microservicios/monolito/serverless)
    - Define infraestructura
    - Propone patrones de diseño
    - Genera descripciones de diagramas
    ↓
[4] Validator & Aggregator Agent
    - Verifica coherencia requisitos-tech-arquitectura
    - Identifica riesgos y conflictos
    - Valida viabilidad
    - Consolida informe final
    ↓
Output estructurado (JSON + Markdown)
```

### Sistema de Memoria Compartida

- **Vector Database (Qdrant)** para almacenar conocimiento técnico:
  - Documentación de frameworks
  - Patrones arquitectónicos
  - Mejores prácticas
  - Ejemplos de arquitecturas previas
- Los agentes consultan esta memoria para enriquecer análisis
- Modo embedded (sin servidor externo)

## 🛠️ Stack Tecnológico

### Core
- **Python 3.11+**: Lenguaje principal
- **LangGraph**: Framework de orquestación de agentes (estándar industria)
- **FastAPI**: API REST para interacción con el sistema
- **Qdrant**: Vector store para memoria compartida (modo embedded)

### LLMs (Flexible - Experimentar)
- **OpenAI GPT-4o**: Agente principal para tareas complejas
- **Anthropic Claude 3.5 Sonnet**: Alternativa/comparación
- **Llama 3.1 (local con Ollama)**: Opcional para reducir costes API

### Infraestructura
- **Docker + Docker Compose**: Containerización completa
- **Pydantic**: Validación y modelos de datos
- **pytest**: Testing (coverage ~60-70%)
- **LangSmith**: Observabilidad y debugging de agentes (tier gratuito)

### Demo/Interfaz
- **Streamlit** o **HTML/CSS/JS vanilla**: Interfaz web simple para demos
- Todo desplegable localmente

## 📁 Estructura de Proyecto Sugerida

```
tfg-multiagent-architect/
├── README.md
├── pyproject.toml / requirements.txt
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── config.py                 # Configuración y variables de entorno
│   ├── main.py                   # Entry point FastAPI
│   │
│   ├── agents/                   # Agentes individuales
│   │   ├── __init__.py
│   │   ├── base.py               # Clase base de agente
│   │   ├── planner.py
│   │   ├── requirements_tech_stack.py
│   │   ├── architecture_designer.py
│   │   └── validator_aggregator.py
│   │
│   ├── orchestration/            # Orquestación con LangGraph
│   │   ├── __init__.py
│   │   ├── graph.py              # Definición del grafo de agentes
│   │   └── state.py              # Estado compartido entre agentes
│   │
│   ├── memory/                   # Sistema de memoria vectorial
│   │   ├── __init__.py
│   │   ├── vector_store.py       # Wrapper de Qdrant
│   │   └── embeddings.py         # Generación de embeddings
│   │
│   ├── llm/                      # Integración con LLMs
│   │   ├── __init__.py
│   │   ├── providers.py          # OpenAI, Claude, Ollama
│   │   └── prompts.py            # Plantillas de prompts
│   │
│   ├── models/                   # Modelos Pydantic
│   │   ├── __init__.py
│   │   ├── input.py              # Modelos de entrada
│   │   └── output.py             # Modelos de salida
│   │
│   ├── api/                      # Endpoints FastAPI
│   │   ├── __init__.py
│   │   └── routes.py
│   │
│   └── utils/                    # Utilidades
│       ├── __init__.py
│       ├── logging.py
│       └── parsers.py
│
├── data/                         # Datos y conocimiento
│   ├── knowledge_base/           # Corpus técnico para embeddings
│   │   ├── frameworks/
│   │   ├── patterns/
│   │   └── architectures/
│   └── test_cases/               # Casos de prueba
│
├── tests/                        # Tests
│   ├── __init__.py
│   ├── test_agents/
│   ├── test_orchestration/
│   └── test_integration/
│
├── notebooks/                    # Jupyter notebooks para experimentación
│   └── experiments/
│
├── frontend/                     # Interfaz demo (Streamlit o HTML)
│   ├── app.py                    # Streamlit app
│   └── static/                   # Assets si usamos HTML
│
└── docs/                         # Documentación adicional
    ├── architecture.md
    └── api_reference.md
```

## 🎯 Objetivos Técnicos Clave

### 1. Sistema Baseline (Mono-Agente)
- Implementar primero un sistema mono-agente simple como **baseline de comparación**
- Prompt único que intente resolver toda la tarea
- Sirve para validar infraestructura y medir mejora del multi-agente

### 2. Sistema Multi-Agente
- Implementación de los 4 agentes con LangGraph
- Comunicación mediante estado compartido
- Integración con memoria vectorial
- Manejo robusto de errores

### 3. Experimentación y Evaluación
- Comparar mono-agente vs multi-agente
- Evaluar diferentes LLMs (GPT-4, Claude, Llama)
- Métricas:
  - **Cualitativas**: Coherencia técnica, completitud, justificación
  - **Cuantitativas**: Latencia, coste API, tokens consumidos
- Análisis con LangSmith (trazas de ejecución)

### 4. Observabilidad
- Logging estructurado en todos los agentes
- Integración con LangSmith para debugging
- Métricas de rendimiento por agente

## 🔧 Aspectos de Implementación

### Prompts
- Cada agente tiene prompts especializados en su dominio
- Sistema de templates con variables (frameworks, requisitos, etc.)
- Iteración y optimización constante de prompts

### Memoria Vectorial
- Qdrant en modo embedded (sin servidor separado)
- Embeddings con OpenAI text-embedding-3-small (o similar)
- Retrieval semántico con top-k documentos relevantes
- Integración en contexto de cada agente

### API REST
- Endpoint principal: `POST /analyze-project`
  - Input: Descripción del proyecto (texto/JSON)
  - Output: Análisis completo estructurado
- Endpoint de streaming (opcional): `POST /analyze-project/stream`
  - WebSocket para visualización en tiempo real
- Endpoint de health check

### Docker
- Servicio FastAPI
- Servicio Qdrant (o embedded en mismo container)
- Servicio Ollama (opcional, si usamos Llama local)
- Volúmenes para persistencia de datos

## 🚀 Fases de Desarrollo

### Fase Actual: Setup y Baseline
0. Crear Estructura de Archivos
1. Configurar entorno de desarrollo (Python, Docker, Git)
2. Implementar infraestructura base (FastAPI + Qdrant)
3. Desarrollar sistema mono-agente baseline
4. Validar flujo end-to-end básico

### Próximas Fases
- Implementación multi-agente con LangGraph
- Sistema de memoria vectorial completo
- Experimentación y optimización
- Interfaz de demo

## 💡 Consideraciones Importantes

### Presupuesto
- **Límite total: ~30€** en APIs
- Usar caché de prompts para reducir costes
- Usar LLM OpenSource en local para desarrollo/testing
- Monitorizar consumo semanalmente

### Testing
- Coverage objetivo: 60-70% (no hace falta 100%)
- Tests de integración más importantes que unitarios
- Validar outputs de agentes con casos reales

### Observabilidad
- LangSmith es **clave** para debugging y análisis
- Logs estructurados desde el inicio
- Métricas de cada agente (tiempo, tokens, coste)

### Fuera de Alcance
- ❌ Generación automática de código completo
- ❌ Deploy en cloud público (AWS/Azure/GCP)
- ❌ Sistema productivo multi-tenant
- ❌ Integración con Jira/GitHub Issues
- ❌ Generación de diagramas visuales (solo descripciones)
- ❌ Fine-tuning de modelos

## 🎓 Aspectos Académicos

Este es un **TFG profesionalizante** con fuerte componente técnico:
- Incluye comparación empírica (mono vs multi-agente)
- Evaluación de diferentes LLMs
- Contribución práctica a automatización de arquitectura software
- Stack alineado con demanda laboral actual (LangGraph, FastAPI, Docker)

## 📚 Referencias Técnicas Clave

- LangChain/LangGraph Documentation
- "Building Multi-Agent Systems with LangGraph" (LangChain Blog)
- Papers: AutoGPT, BabyAGI, MetaGPT
- Qdrant Documentation
- FastAPI Documentation

---

**Nota para Claude Code:** Este proyecto es flexible y evolutivo. Las decisiones técnicas pueden ajustarse durante el desarrollo según necesidades y resultados experimentales. Prioriza siempre funcionalidad core sobre features opcionales.