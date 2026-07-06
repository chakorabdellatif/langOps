"""LangOps OTel attribute names — mirrors docs/semantic-conventions.md.

Never invent an attribute name inline: add it to the conventions document
first, then here, then to the backend constants. CI fails on drift.
"""

SCHEMA_VERSION = "0.1.0"

# ── Resource attributes ────────────────────────────────────────────────
SDK_VERSION = "langops.sdk.version"
PROJECT = "langops.project"

# ── Span kind discriminator ────────────────────────────────────────────
KIND = "langops.kind"


class Kind:
    EXECUTION = "execution"
    NODE = "node"
    LLM = "llm"
    TOOL = "tool"


# ── Execution spans ────────────────────────────────────────────────────
EXECUTION_ID = "langops.execution.id"
GRAPH_NAME = "langops.graph.name"
GRAPH_TOPOLOGY_HASH = "langops.graph.topology_hash"
THREAD_ID = "langops.thread.id"
CHECKPOINT_ID = "langops.checkpoint.id"
CHECKPOINT_PARENT_ID = "langops.checkpoint.parent_id"
CHECKPOINT_RESUMED = "langops.checkpoint.resumed"

# Execution span events
EVENT_GRAPH_TOPOLOGY = "langops.graph.topology"
EVENT_EXECUTION_INPUT = "langops.execution.input"
EVENT_EXECUTION_OUTPUT = "langops.execution.output"

# ── Node spans ─────────────────────────────────────────────────────────
NODE_NAME = "langops.node.name"
NODE_SEQUENCE = "langops.node.sequence"
NODE_RETRY_COUNT = "langops.node.retry_count"

# Node span events
EVENT_STATE_INPUT = "langops.state.input"
EVENT_STATE_OUTPUT = "langops.state.output"
EVENT_STATE_DIFF = "langops.state.diff"
EVENT_STATE_SNAPSHOT = "langops.state.snapshot"
STATE_SIZE_BYTES = "langops.state.size_bytes"
STATE_MESSAGE_COUNT = "langops.state.message_count"

# ── LLM spans (official GenAI conventions where they exist) ───────────
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

# LLM span events
EVENT_LLM_MESSAGES = "langops.llm.messages"
EVENT_LLM_PARAMS = "langops.llm.params"
EVENT_LLM_RESPONSE = "langops.llm.response"

# ── Tool spans ─────────────────────────────────────────────────────────
TOOL_NAME = "langops.tool.name"
EVENT_TOOL_INPUT = "langops.tool.input"
EVENT_TOOL_OUTPUT = "langops.tool.output"

# ── Cross-cutting ──────────────────────────────────────────────────────
TRUNCATED = "langops.truncated"
