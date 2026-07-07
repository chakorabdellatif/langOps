"""Backend mirror of docs/semantic-conventions.md (see sdk/src/langops/semconv.py).

Never invent an attribute name inline — the conventions doc changes first.
"""

SDK_VERSION = "langops.sdk.version"
PROJECT = "langops.project"

KIND = "langops.kind"
KIND_EXECUTION = "execution"
KIND_NODE = "node"
KIND_LLM = "llm"
KIND_TOOL = "tool"

EXECUTION_ID = "langops.execution.id"
GRAPH_NAME = "langops.graph.name"
GRAPH_TOPOLOGY_HASH = "langops.graph.topology_hash"
THREAD_ID = "langops.thread.id"
CHECKPOINT_ID = "langops.checkpoint.id"
CHECKPOINT_PARENT_ID = "langops.checkpoint.parent_id"
CHECKPOINT_RESUMED = "langops.checkpoint.resumed"

EVENT_GRAPH_TOPOLOGY = "langops.graph.topology"
EVENT_EXECUTION_INPUT = "langops.execution.input"
EVENT_EXECUTION_OUTPUT = "langops.execution.output"

NODE_NAME = "langops.node.name"
NODE_SEQUENCE = "langops.node.sequence"
NODE_RETRY_COUNT = "langops.node.retry_count"
NODE_CATEGORY = "langops.node.category"

# Node categories (v0.2). Structural ones (router/conditional/checkpoint/
# subgraph) come from the SDK topology; llm/tool/utility are inferred from
# child spans during ingestion when the SDK does not send a category.
NODE_CATEGORY_LLM = "llm"
NODE_CATEGORY_TOOL = "tool"
NODE_CATEGORY_UTILITY = "utility"
NODE_CATEGORY_ROUTER = "router"
NODE_CATEGORY_CONDITIONAL = "conditional"
NODE_CATEGORY_CHECKPOINT = "checkpoint"
NODE_CATEGORY_SUBGRAPH = "subgraph"
_STRUCTURAL_CATEGORIES = frozenset(
    {
        NODE_CATEGORY_ROUTER,
        NODE_CATEGORY_CONDITIONAL,
        NODE_CATEGORY_CHECKPOINT,
        NODE_CATEGORY_SUBGRAPH,
    }
)

EVENT_STATE_INPUT = "langops.state.input"
EVENT_STATE_OUTPUT = "langops.state.output"
EVENT_STATE_DIFF = "langops.state.diff"
EVENT_STATE_SNAPSHOT = "langops.state.snapshot"
STATE_SIZE_BYTES = "langops.state.size_bytes"
STATE_MESSAGE_COUNT = "langops.state.message_count"

GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

EVENT_LLM_MESSAGES = "langops.llm.messages"
EVENT_LLM_PARAMS = "langops.llm.params"
EVENT_LLM_RESPONSE = "langops.llm.response"

TOOL_NAME = "langops.tool.name"
EVENT_TOOL_INPUT = "langops.tool.input"
EVENT_TOOL_OUTPUT = "langops.tool.output"

# Structured logs (v0.2)
EVENT_LOG = "langops.log"
LOG_LEVEL = "langops.log.level"
LOG_LOGGER = "langops.log.logger"
LOG_SOURCE = "langops.log.source"

LOG_SOURCE_APP = "app"
LOG_SOURCE_SDK = "sdk"
LOG_SOURCE_LLM = "llm"
LOG_SOURCE_TOOL = "tool"
LOG_SOURCE_EXCEPTION = "exception"

# Execution replay (v0.2)
EXECUTION_REPLAY_OF = "langops.execution.replay_of"
EVENT_EXECUTION_OVERRIDES = "langops.execution.overrides"

# Event payloads ride as a JSON string under this event attribute.
PAYLOAD = "langops.payload"
TRUNCATED = "langops.truncated"

EVENT_EXCEPTION = "exception"
EXCEPTION_TYPE = "exception.type"
EXCEPTION_MESSAGE = "exception.message"
EXCEPTION_STACKTRACE = "exception.stacktrace"
