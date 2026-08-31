# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the single normalization pass — including adversarial tests."""

import json
from pathlib import Path
import pytest
from agentic_otel.normalize import OTELNormalizer, NormalizedTrace
from agentic_otel.classifier import SpanType, Framework

TRACES = Path(__file__).parent / "traces"
SOURCE_MAP = {
    "lookup_formulary": {"source_name": "formulary-db", "source_type": "database"},
    "check_coverage": {"source_name": "coverage-policy", "source_type": "api"},
}

def load(name):
    with open(TRACES / name) as f:
        return json.load(f)


class TestNormalizeValidTrace:
    @pytest.fixture
    def trace(self):
        return OTELNormalizer(tool_source_map=SOURCE_MAP).normalize(load("valid_claim.json"))

    def test_execution_id(self, trace):
        assert trace.execution_id != "unknown"

    def test_has_spans(self, trace):
        assert len(trace.spans) > 0

    def test_tool_calls(self, trace):
        tools = trace.tool_calls()
        names = {t.name for t in tools}
        assert "lookup_formulary" in names
        assert "check_coverage" in names

    def test_model_calls(self, trace):
        assert len(trace.model_calls()) >= 1

    def test_data_sources(self, trace):
        sources = trace.data_source_names()
        assert "formulary-db" in sources
        assert "coverage-policy" in sources

    def test_classification_confidence(self, trace):
        for span in trace.tool_calls():
            assert span.classification_confidence >= 0.5
        for span in trace.model_calls():
            assert span.classification_confidence >= 0.5

    def test_spans_sorted_by_time(self, trace):
        """R3: Spans should be sorted by start time."""
        times = [s.start_time for s in trace.spans]
        assert times == sorted(times)

    def test_token_usage(self, trace):
        total = trace.total_tokens()
        assert total.input_tokens > 0
        assert total.output_tokens > 0

    def test_no_validation_errors(self, trace):
        # Valid trace should have no critical errors
        critical = [e for e in trace.validation_errors if "unknown" in e]
        assert len(critical) == 0


class TestNormalizeViolation:
    @pytest.fixture
    def trace(self):
        return OTELNormalizer(tool_source_map=SOURCE_MAP).normalize(load("violation_parametric_only.json"))

    def test_no_tool_calls(self, trace):
        assert len(trace.tool_calls()) == 0

    def test_no_data_sources(self, trace):
        assert len(trace.data_source_names()) == 0

    def test_has_model_call(self, trace):
        assert len(trace.model_calls()) >= 1


class TestNormalizeMultiFramework:
    @pytest.fixture(params=["framework_strands.json", "framework_langchain.json", "framework_pydantic_ai.json"])
    def trace(self, request):
        return OTELNormalizer(tool_source_map=SOURCE_MAP).normalize(load(request.param))

    def test_has_tool_calls(self, trace):
        assert len(trace.tool_calls()) >= 1

    def test_data_sources_mapped(self, trace):
        assert "formulary-db" in trace.data_source_names()


# --- Adversarial Tests from the Audit ---

class TestAdversarial:
    def test_multiple_root_spans(self):
        """Audit Test 1: Trace with multiple root spans."""
        trace = {"resourceSpans": [{"scopeSpans": [{"spans": [
            {"spanId": "A", "parentSpanId": "", "traceId": "t1", "name": "agent_1",
             "startTimeUnixNano": "1", "attributes": []},
            {"spanId": "B", "parentSpanId": "", "traceId": "t2", "name": "agent_2",
             "startTimeUnixNano": "2", "attributes": []},
            {"spanId": "C", "parentSpanId": "B", "name": "tool_call",
             "startTimeUnixNano": "3",
             "attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "execute_tool"}},
                            {"key": "gen_ai.tool.name", "value": {"stringValue": "my_tool"}}]},
        ]}]}]}
        result = OTELNormalizer().normalize(trace)
        # Should not crash. Root is the first one (A).
        assert result.execution_id in ("t1", "t2")
        # Tool call should be present
        tools = result.tool_calls()
        assert len(tools) >= 1

    def test_missing_token_attributes(self):
        """Audit Test 4: Model call with no token attributes."""
        trace = {"resourceSpans": [{"scopeSpans": [{"spans": [
            {"spanId": "root", "parentSpanId": "", "traceId": "t1",
             "startTimeUnixNano": "1", "attributes": []},
            {"spanId": "model", "parentSpanId": "root",
             "startTimeUnixNano": "2",
             "attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
                            {"key": "gen_ai.request.model", "value": {"stringValue": "claude"}}]},
        ]}]}]}
        result = OTELNormalizer().normalize(trace)
        models = result.model_calls()
        assert len(models) == 1
        # Token usage should be None (not 0)
        assert models[0].token_usage is None

    def test_empty_trace(self):
        """Empty trace should produce validation errors."""
        result = OTELNormalizer().normalize({"resourceSpans": []})
        assert result.execution_id == "unknown"
        assert len(result.validation_errors) > 0
        assert any("No spans" in e for e in result.validation_errors)

    def test_snake_case_trace(self):
        """Snake_case OTLP format should work identically."""
        trace = {"resource_spans": [{"scope_spans": [{"spans": [
            {"spanId": "root", "parent_span_id": "", "traceId": "t1",
             "startTimeUnixNano": "1", "attributes": []},
            {"spanId": "tool", "parent_span_id": "root",
             "startTimeUnixNano": "2",
             "attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "execute_tool"}},
                            {"key": "gen_ai.tool.name", "value": {"stringValue": "my_tool"}}]},
        ]}]}]}
        result = OTELNormalizer().normalize(trace)
        assert len(result.tool_calls()) == 1

    def test_out_of_order_spans(self):
        """Audit Test 2: Spans arrive out of temporal order."""
        trace = {"resourceSpans": [{"scopeSpans": [{"spans": [
            {"spanId": "root", "parentSpanId": "", "traceId": "t1",
             "startTimeUnixNano": "1", "attributes": []},
            # Arrive out of order: C, A, B
            {"spanId": "C", "parentSpanId": "root", "startTimeUnixNano": "300",
             "attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "execute_tool"}},
                            {"key": "gen_ai.tool.name", "value": {"stringValue": "tool_c"}}]},
            {"spanId": "A", "parentSpanId": "root", "startTimeUnixNano": "100",
             "attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "execute_tool"}},
                            {"key": "gen_ai.tool.name", "value": {"stringValue": "tool_a"}}]},
            {"spanId": "B", "parentSpanId": "root", "startTimeUnixNano": "200",
             "attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "execute_tool"}},
                            {"key": "gen_ai.tool.name", "value": {"stringValue": "tool_b"}}]},
        ]}]}]}
        result = OTELNormalizer().normalize(trace)
        # R3: Spans should be sorted by timestamp, not array order
        tool_names = [s.name for s in result.tool_calls()]
        assert tool_names == ["tool_a", "tool_b", "tool_c"]

    def test_framework_specific_operation_with_registry(self):
        """Custom operation names can be registered."""
        normalizer = OTELNormalizer()
        normalizer.registry.register_model_op("generate")
        trace = {"resourceSpans": [{"scopeSpans": [{"spans": [
            {"spanId": "root", "parentSpanId": "", "traceId": "t1",
             "startTimeUnixNano": "1", "attributes": []},
            {"spanId": "model", "parentSpanId": "root", "startTimeUnixNano": "2",
             "attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "generate"}}]},
        ]}]}]}
        result = normalizer.normalize(trace)
        assert len(result.model_calls()) == 1
        assert result.model_calls()[0].classification_confidence == 1.0
