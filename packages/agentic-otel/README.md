# agentic-otel

**Normalization layer for OpenTelemetry GenAI agent traces. Parse once, analyze anywhere.**

```bash
pip install agentic-otel
```

## Why this exists

Every tool that analyzes AI agent traces re-implements the same parsing: span extraction, root finding, attribute parsing, timestamp handling, span classification. And every agent framework emits slightly different OTEL: camelCase vs. snake_case keys, KV-list vs. dict attributes, content in span attributes vs. span events, different operation names.

`agentic-otel` does that parsing once, correctly, with zero runtime dependencies — so trace-analysis tools can start from a consistent representation instead of raw JSON.

## What it does

```python
from agentic_otel import (
    extract_spans,      # OTLP resourceSpans or flat {"spans": [...]} -> list of span dicts
    find_root,          # locate the root span (parent-less, or earliest fallback)
    parse_attrs,        # KV-list or dict attributes -> flat dict
    parse_timestamp,    # unix nanos (int or str) -> datetime
    DEFAULT_REGISTRY,   # span classification rules
)

spans = extract_spans(raw_trace_json)
root = find_root(spans)

for span in spans:
    result = DEFAULT_REGISTRY.classify(span)
    print(span.get("name"), "->", result.span_type, f"(confidence: {result.confidence})")
    # execute_tool lookup_formulary -> SpanType.TOOL_CALL (confidence: high)
```

### Span classification

Spans are classified against the OTEL GenAI semantic conventions (`gen_ai.operation.name`, `gen_ai.tool.name`, `gen_ai.request.model`, ...) into: `TOOL_CALL`, `MODEL_CALL`, `RETRIEVAL`, `AGENT_INVOCATION`, `EVENT_LOOP`, `HUMAN_REVIEW`, or `CUSTOM` — each with a confidence score and the reason for the classification.

### Framework detection

Traces are fingerprinted to the framework that produced them — Strands Agents, LangChain/LangGraph, PydanticAI, Claude Agent SDK — so downstream tools can handle framework-specific quirks (e.g., where message content lives) without their own detection logic.

### Extensibility

Classification rules live in a `SemanticConventionRegistry`. New frameworks, operation names, or attribute conventions are added as registry entries, not code changes:

```python
from agentic_otel import SemanticConventionRegistry

registry = SemanticConventionRegistry()
registry.register_tool_op("my_framework.tool_exec")
result = registry.classify(span)
framework = registry.detect_framework(raw_trace_json)
```

### Normalized trace model

For tools that want a fully structured representation, `OTELNormalizer` produces a `NormalizedTrace` — typed `NormalizedSpan` entries with token usage, data source references, resolved parent/child relationships, and extracted input/output text — from a single parsing pass:

```python
from agentic_otel import OTELNormalizer

trace = OTELNormalizer().normalize(raw_trace_json)
```

## Format tolerance

Handles, without configuration:

- OTLP `resourceSpans` exports and flat `{"spans": [...]}` dumps
- Attribute lists (`[{"key": ..., "value": {"stringValue": ...}}]`) and flat dicts
- `camelCase` and `snake_case` span field names (`traceId` / `trace_id`)
- Message content in span attributes or span events
- Nanosecond timestamps as integers or strings

## Support and stability

This is a community open source project, not an AWS service or product.

- **Support:** community only, via GitHub issues. It is not covered by AWS Support plans, and there is no SLA.
- **Stability:** pre-1.0 and published with the `Development Status :: 4 - Beta` classifier. The API may change between minor versions; pin a version if you depend on it.
- **Warranty:** provided "AS IS", without warranties or conditions of any kind, as stated in the [Apache License 2.0](LICENSE) (Sections 7 and 8).

You are responsible for evaluating whether it fits your own compliance and operational requirements before relying on it.

## License

Apache-2.0
