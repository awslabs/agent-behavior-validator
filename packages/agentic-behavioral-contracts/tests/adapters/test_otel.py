# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the OTEL trace adapter."""

import json
from pathlib import Path

from agent_validator.adapters.otel import OTELAdapter
from agent_validator.models import StepType

SAMPLE_DIR = Path(__file__).parent.parent.parent / "examples" / "sample_traces"

TOOL_SOURCE_MAP = {
    "lookup_formulary": {"source_name": "formulary-db", "source_type": "database"},
    "check_coverage": {"source_name": "coverage-policy", "source_type": "api"},
}


def _load_trace(name: str) -> dict:
    with open(SAMPLE_DIR / name) as f:
        return json.load(f)


class TestOTELAdapterValidTrace:
    def setup_method(self):
        self.adapter = OTELAdapter(tool_source_map=TOOL_SOURCE_MAP)
        self.raw = _load_trace("valid_claim.json")
        self.execution = self.adapter.normalize(self.raw)

    def test_execution_id(self):
        assert self.execution.execution_id == "trace-valid-001"

    def test_trace_source(self):
        assert self.execution.trace_source == "otel"

    def test_step_count(self):
        # 5 child spans (2 model calls + 3 tool calls), root excluded
        assert len(self.execution.steps) == 5

    def test_tool_calls_extracted(self):
        tools = self.execution.tool_calls()
        assert len(tools) == 3
        tool_names = [t.name for t in tools]
        assert "lookup_formulary" in tool_names
        assert "check_coverage" in tool_names
        assert "render_decision" in tool_names

    def test_model_calls_extracted(self):
        models = self.execution.model_calls()
        assert len(models) == 2

    def test_data_sources_mapped(self):
        sources = self.execution.data_source_names()
        assert "formulary-db" in sources
        assert "coverage-policy" in sources

    def test_tool_inputs_parsed(self):
        tools = self.execution.tool_calls()
        formulary_tool = next(t for t in tools if t.name == "lookup_formulary")
        assert formulary_tool.inputs == {"drug_name": "lisinopril"}

    def test_tool_outputs_parsed(self):
        tools = self.execution.tool_calls()
        formulary_tool = next(t for t in tools if t.name == "lookup_formulary")
        assert formulary_tool.outputs["status"] == "covered"
        assert formulary_tool.outputs["policy_section"] == "Section 4.2.1"

    def test_input_text_extracted(self):
        assert self.execution.input_text is not None
        assert "MEM-001" in self.execution.input_text
        assert "lisinopril" in self.execution.input_text

    def test_output_text_extracted(self):
        assert self.execution.output_text is not None
        assert "Section 4.2.1" in self.execution.output_text

    def test_resource_attrs(self):
        assert self.execution.metadata.get("service.name") == "claims-processing-agent"


class TestOTELAdapterInvalidTrace:
    def setup_method(self):
        self.adapter = OTELAdapter(tool_source_map=TOOL_SOURCE_MAP)
        self.raw = _load_trace("invalid_claim.json")
        self.execution = self.adapter.normalize(self.raw)

    def test_no_tool_calls(self):
        tools = self.execution.tool_calls()
        assert len(tools) == 0

    def test_only_model_call(self):
        models = self.execution.model_calls()
        assert len(models) == 1

    def test_no_data_sources(self):
        assert self.execution.data_source_names() == set()

    def test_output_lacks_citations(self):
        assert self.execution.output_text is not None
        assert "Section" not in self.execution.output_text


class TestOTELAdapterEmptyTrace:
    def test_empty_trace(self):
        adapter = OTELAdapter()
        execution = adapter.normalize({"resourceSpans": []})
        assert execution.execution_id == "unknown"
        assert execution.steps == []


class TestOTELAdapterToolSourceMap:
    def test_unmapped_tool_has_no_data_sources(self):
        adapter = OTELAdapter(tool_source_map={})
        raw = _load_trace("valid_claim.json")
        execution = adapter.normalize(raw)
        assert execution.data_source_names() == set()

    def test_partial_mapping(self):
        adapter = OTELAdapter(
            tool_source_map={"lookup_formulary": {"source_name": "formulary-db", "source_type": "database"}}
        )
        raw = _load_trace("valid_claim.json")
        execution = adapter.normalize(raw)
        assert "formulary-db" in execution.data_source_names()
        assert "coverage-policy" not in execution.data_source_names()
