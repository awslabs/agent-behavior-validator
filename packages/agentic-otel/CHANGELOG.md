# Changelog

## 0.1.0 (unreleased)

Initial release.

- Single-pass OTEL JSON parsing: span extraction (OTLP resourceSpans and flat
  formats), root finding, attribute parsing (KV-list and dict formats,
  camelCase and snake_case keys), timestamp handling.
- Span classification against GenAI semantic conventions with confidence
  scores: tool calls, model calls, retrievals, agent invocations, event
  loops.
- Framework detection for Strands Agents, LangChain/LangGraph, PydanticAI,
  and Claude Agent SDK traces.
- Extensible `SemanticConventionRegistry` for additional frameworks and
  operation names.
- `NormalizedTrace` model for downstream analysis tools.
- Zero runtime dependencies.
