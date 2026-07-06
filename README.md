# LangOps

> **A lightweight observability and evaluation platform for LangGraph applications.**

LangOps is an open-source developer platform that provides deep observability, debugging, and evaluation capabilities for **LangGraph-based AI applications**.

Instead of replacing LangGraph, LangOps integrates seamlessly into existing projects to help developers understand what happens inside their agent workflows. It automatically captures graph executions, node transitions, LLM calls, state changes, token usage, costs, latency, tool invocations, and execution logs, all accessible through a modern web dashboard.

The goal of LangOps is to become the equivalent of **Chrome DevTools for LangGraph**, allowing developers to monitor, debug, replay, and optimize complex multi-agent systems.

---

# MVP Goals

The first version focuses on **observability**, not orchestration.

LangOps aims to answer questions such as:

- Which node failed?
- How much did this execution cost?
- How many tokens did each agent consume?
- What prompt was sent to the model?
- What response was returned?
- How did the graph state evolve?
- Which node is the performance bottleneck?

---

# Features

## Graph Execution Monitoring

- Automatic instrumentation of LangGraph applications
- Trace every graph execution
- Execution history
- Node execution timeline
- Interactive graph visualization

---

## Agent & Node Inspection

For every node execution:

- Execution status
- Execution duration
- Start & end timestamps
- Retry count
- Error details
- Tool invocations
- State before execution
- State after execution
- State diff visualization

---

## LLM Observability

Capture every LLM request:

- Model used
- System prompt
- User prompt
- Messages
- Parameters (temperature, max tokens, etc.)
- Full request payload
- Full response payload

---

## Token & Cost Tracking

Automatically calculate:

- Input tokens
- Output tokens
- Total tokens
- Cost per request
- Cost per node
- Cost per graph execution
- Cost statistics

---

## Context & State Observation

LangOps provides deep visibility into how the **LangGraph State** evolves during execution.

For every node, it captures:

- Initial and final state
- State diff (added, modified, removed values)
- Context growth (messages, memory, retrieved documents)
- Thread and checkpoint information
- Whether the execution started fresh or resumed from a previous checkpoint

This allows developers to understand exactly how each agent contributes to the workflow and how context evolves across the graph.

---

## Execution Dashboard

View:

- Recent executions
- Execution timeline
- Node graph
- Latency metrics
- Cost metrics
- Token usage
- Failure rate

---

## Logging & Debugging

- Structured logs
- Error tracking
- Stack traces
- Tool execution logs

---

## REST API

Expose execution data through a FastAPI backend for integration with external tools.

---

# Future Roadmap

The MVP intentionally focuses on observability.

Future releases may include:

- Prompt versioning
- Prompt comparison
- Agent evaluation
- Execution replay
- Human-in-the-loop support
- Checkpoint visualization
- Time travel debugging
- Multi-project support
- Team collaboration
- LangSmith import/export

---

# Architecture

```
                LangGraph Application
                        │
                langops.instrument()
                        │
                        ▼
               LangOps Instrumentation SDK
                        │
                OpenTelemetry SDK
                        │
                        ▼
            OpenTelemetry Collector
                        │
                        ▼
                 FastAPI Backend
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
     PostgreSQL                   Redis
          │
          ▼
      REST API
          │
          ▼
     Next.js Dashboard
```

---

# Project Structure

```
langops/

├── sdk/                 # LangGraph instrumentation SDK
├── backend/             # FastAPI server
├── dashboard/           # Next.js frontend
├── collector/           # OpenTelemetry configuration
├── docker/
├── docker-compose.yml
└── README.md
```

---

# Tech Stack

## Backend

- Python 3.12
- FastAPI
- SQLAlchemy
- Pydantic
- AsyncIO

---

## AI Integration

- LangGraph
- LangChain
- OpenAI SDK

---

## Observability

- OpenTelemetry SDK
- OpenTelemetry Collector

---

## Database

- PostgreSQL

---

## Cache & Messaging

- Redis

---

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Flow
- Recharts

---

## DevOps

- Docker
- Docker Compose
- GitHub Actions

---

# Deployment

The MVP is fully containerized using **Docker Compose**.

Services:

- langops-api
- langops-dashboard
- postgres
- redis
- otel-collector

Future releases will support Kubernetes deployments.

---

# Getting Started

## Clone the repository

```bash
git clone https://github.com/yourusername/langops.git

cd langops
```

---

## Start all services

```bash
docker compose up --build
```

---

## Services

| Service | URL |
|----------|-----|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

# Instrumenting a LangGraph Application

Install the SDK:

```bash
pip install langops
```

Enable monitoring:

```python
from langops import instrument

instrument(graph)

graph.invoke(...)
```

Once enabled, every graph execution is automatically captured and appears in the LangOps dashboard.

---

# Design Principles

LangOps follows four core principles:

- **Simple** — minimal setup with sensible defaults.
- **Lightweight** — low runtime overhead and easy integration.
- **Developer-first** — built for debugging and understanding agent workflows.
- **Framework-aware** — deeply integrated with LangGraph instead of providing generic abstractions.

---

# Vision

LangOps aims to become the observability layer for LangGraph applications by providing developers with the tools needed to inspect, monitor, debug, and optimize AI agent workflows from local development to production.
