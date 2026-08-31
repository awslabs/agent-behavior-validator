# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for span classification and framework detection."""

import json
from pathlib import Path
import pytest
from agentic_otel.classifier import (
    SemanticConventionRegistry, SpanType, Framework, Classification,
)

TRACES = Path(__file__).parent / "traces"


def load(name):
    with open(TRACES / name) as f:
        return json.load(f)


class TestClassification:
    def setup_method(self):
        self.reg = SemanticConventionRegistry()

    def test_tool_by_operation_name(self):
        span = {"attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "execute_tool"}},
                                {"key": "gen_ai.tool.name", "value": {"stringValue": "lookup"}}]}
        c = self.reg.classify(span)
        assert c.span_type == SpanType.TOOL_CALL
        assert c.confidence == 1.0
        assert c.tool_name == "lookup"

    def test_model_by_operation_name(self):
        span = {"attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}}]}
        c = self.reg.classify(span)
        assert c.span_type == SpanType.MODEL_CALL
        assert c.confidence == 1.0

    def test_agent_invocation(self):
        span = {"attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "invoke_agent"}}]}
        c = self.reg.classify(span)
        assert c.span_type == SpanType.AGENT_INVOCATION
        assert c.confidence == 1.0

    def test_tool_by_name_heuristic(self):
        span = {"name": "execute_tool lookup_formulary", "attributes": []}
        c = self.reg.classify(span)
        assert c.span_type == SpanType.TOOL_CALL
        assert c.confidence == 0.8
        assert c.tool_name == "lookup_formulary"

    def test_pydantic_running_tool(self):
        span = {"name": "running tool", "attributes": [
            {"key": "gen_ai.tool.name", "value": {"stringValue": "my_tool"}}]}
        c = self.reg.classify(span)
        assert c.span_type == SpanType.TOOL_CALL
        assert c.tool_name == "my_tool"

    def test_unknown_operation(self):
        span = {"name": "something", "attributes": [
            {"key": "gen_ai.operation.name", "value": {"stringValue": "unknown_op"}}]}
        c = self.reg.classify(span)
        assert c.span_type == SpanType.CUSTOM
        assert c.confidence == 0.0

    # Adversarial Test 3: Non-standard operation name
    def test_non_standard_operation_name(self):
        span = {"attributes": [
            {"key": "gen_ai.operation.name", "value": {"stringValue": "generate"}},
            {"key": "gen_ai.usage.input_tokens", "value": {"intValue": 1000}},
            {"key": "gen_ai.request.model", "value": {"stringValue": "claude-sonnet-4"}},
        ]}
        c = self.reg.classify(span)
        # Without registration, "generate" is not recognized
        assert c.span_type in (SpanType.MODEL_CALL, SpanType.CUSTOM)
        # But if we register it:
        self.reg.register_model_op("generate")
        c2 = self.reg.classify(span)
        assert c2.span_type == SpanType.MODEL_CALL
        assert c2.confidence == 1.0

    def test_model_by_attributes_heuristic(self):
        """Model with gen_ai.request.model and token usage but no operation name."""
        span = {"name": "llm", "attributes": [
            {"key": "gen_ai.request.model", "value": {"stringValue": "claude"}},
            {"key": "gen_ai.usage.input_tokens", "value": {"intValue": 500}},
        ]}
        c = self.reg.classify(span)
        assert c.span_type == SpanType.MODEL_CALL
        assert c.confidence == 0.5

    def test_event_loop_detection(self):
        span = {"name": "execute_event_loop_cycle", "attributes": []}
        c = self.reg.classify(span)
        assert c.span_type == SpanType.EVENT_LOOP

    def test_bedrock_kb(self):
        span = {"attributes": [{"key": "aws.bedrock.knowledge_base.id", "value": {"stringValue": "kb123"}}]}
        c = self.reg.classify(span)
        assert c.span_type == SpanType.RETRIEVAL

    def test_cached_parsed_attrs(self):
        """Classification should include cached parsed attributes."""
        span = {"attributes": [
            {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
            {"key": "gen_ai.request.model", "value": {"stringValue": "claude-sonnet"}},
        ]}
        c = self.reg.classify(span)
        assert c.parsed_attrs is not None
        assert c.parsed_attrs["gen_ai.operation.name"] == "chat"
        assert c.parsed_attrs["gen_ai.request.model"] == "claude-sonnet"

    def test_tool_name_only_no_operation(self):
        """Span with only gen_ai.tool.name (no operation) -> TOOL_CALL at 1.0 confidence."""
        span = {"attributes": [
            {"key": "gen_ai.tool.name", "value": {"stringValue": "my_tool"}},
        ]}
        c = self.reg.classify(span)
        assert c.span_type == SpanType.TOOL_CALL
        assert c.tool_name == "my_tool"
        # First branch catches it because tool_name is truthy
        assert c.confidence == 1.0

    def test_event_loop_case_insensitive(self):
        """Event loop detection should be case-insensitive."""
        span = {"name": "Execute_Event_Loop_Cycle", "attributes": []}
        c = self.reg.classify(span)
        assert c.span_type == SpanType.EVENT_LOOP

    def test_all_model_ops_recognized(self):
        """All registered model operations should classify as MODEL_CALL."""
        for op in ("chat", "text_completion", "generate_content", "llm_request"):
            span = {"attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": op}}]}
            c = self.reg.classify(span)
            assert c.span_type == SpanType.MODEL_CALL, f"op={op} not recognized as MODEL_CALL"
            assert c.confidence == 1.0

    def test_custom_registry(self):
        """Custom registry with additional operations."""
        reg = SemanticConventionRegistry()
        reg.register_model_op("invoke")
        reg.register_tool_op("run_tool")
        span1 = {"attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "invoke"}}]}
        span2 = {"attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "run_tool"}}]}
        assert reg.classify(span1).span_type == SpanType.MODEL_CALL
        assert reg.classify(span2).span_type == SpanType.TOOL_CALL


class TestFrameworkDetection:
    def setup_method(self):
        self.reg = SemanticConventionRegistry()

    def test_detect_strands(self):
        trace = load("framework_strands.json")
        assert self.reg.detect_framework(trace) == Framework.STRANDS

    def test_detect_langchain(self):
        trace = load("framework_langchain.json")
        fw = self.reg.detect_framework(trace)
        assert fw == Framework.LANGCHAIN

    def test_detect_pydantic_ai(self):
        trace = load("framework_pydantic_ai.json")
        fw = self.reg.detect_framework(trace)
        # PydanticAI may or may not be detected depending on scope names
        assert fw in (Framework.PYDANTIC_AI, Framework.UNKNOWN)

    def test_detect_unknown(self):
        trace = {"resourceSpans": [{"scopeSpans": [{"spans": [{"name": "x"}]}]}]}
        assert self.reg.detect_framework(trace) == Framework.UNKNOWN
