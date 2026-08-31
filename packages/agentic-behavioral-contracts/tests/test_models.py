# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for core data models."""

from agent_validator.models import StepType


def test_tool_calls(valid_claims_execution):
    tools = valid_claims_execution.tool_calls()
    assert len(tools) == 3
    assert all(t.step_type == StepType.TOOL_CALL for t in tools)


def test_model_calls(valid_claims_execution):
    models = valid_claims_execution.model_calls()
    assert len(models) == 2
    assert all(m.step_type == StepType.MODEL_CALL for m in models)


def test_step_names(valid_claims_execution):
    names = valid_claims_execution.step_names()
    assert names == ["chat", "lookup_formulary", "check_coverage", "render_decision", "chat"]


def test_data_source_names(valid_claims_execution):
    sources = valid_claims_execution.data_source_names()
    assert sources == {"formulary-db", "coverage-policy"}


def test_data_source_names_empty(invalid_claims_execution):
    sources = invalid_claims_execution.data_source_names()
    assert sources == set()


def test_all_data_sources(valid_claims_execution):
    sources = valid_claims_execution.all_data_sources()
    assert len(sources) == 2
    source_names = [s.source_name for s in sources]
    assert "formulary-db" in source_names
    assert "coverage-policy" in source_names
