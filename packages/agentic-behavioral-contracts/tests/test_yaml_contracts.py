# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for YAML contract loading: conditions (when:), severity, and
must_not_include_steps -- the mechanisms for contracts with multiple valid
execution paths."""

from __future__ import annotations

import pytest

from agent_validator.contracts.constraints import (
    ConditionalConstraint,
    MustNotIncludeSteps,
    must_not_include_steps,
)
from agent_validator.generate import _build_condition, load_contract_from_yaml
from agent_validator.models import VerdictStatus
from agent_validator.validator import validate


def write_contract(tmp_path, body: str):
    path = tmp_path / "contract.yaml"
    path.write_text(body)
    return path


# ---------------------------------------------------------------------------
# must_not_include_steps
# ---------------------------------------------------------------------------


class TestMustNotIncludeSteps:
    def test_passes_when_forbidden_steps_absent(self, valid_claims_execution):
        result = must_not_include_steps(["delete_records"]).evaluate(valid_claims_execution)
        assert result.passed

    def test_fails_when_forbidden_step_present(self, valid_claims_execution):
        result = must_not_include_steps(["render_decision"]).evaluate(valid_claims_execution)
        assert not result.passed
        assert "render_decision" in result.violation.message
        assert result.violation.evidence["found"] == ["render_decision"]


# ---------------------------------------------------------------------------
# Condition builder
# ---------------------------------------------------------------------------


class TestBuildCondition:
    def test_metadata_condition(self, valid_claims_execution):
        fn, desc = _build_condition({"metadata": {"claim_type": "pharmacy"}})
        assert fn(valid_claims_execution)
        assert "claim_type=pharmacy" in desc
        fn2, _ = _build_condition({"metadata": {"claim_type": "dental"}})
        assert not fn2(valid_claims_execution)

    def test_input_matches_condition(self, valid_claims_execution):
        fn, _ = _build_condition({"input_matches": "pharmacy claim"})
        assert fn(valid_claims_execution)
        fn2, _ = _build_condition({"input_matches": "dental"})
        assert not fn2(valid_claims_execution)

    def test_input_matches_is_case_insensitive(self, valid_claims_execution):
        fn, _ = _build_condition({"input_matches": "PHARMACY"})
        assert fn(valid_claims_execution)

    def test_step_present_condition(self, valid_claims_execution):
        fn, _ = _build_condition({"step_present": "lookup_formulary"})
        assert fn(valid_claims_execution)
        fn2, _ = _build_condition({"step_present": ["escalate", "human_review"]})
        assert not fn2(valid_claims_execution)

    def test_tool_result_matches_condition(self, valid_claims_execution):
        fn, desc = _build_condition(
            {"tool_result_matches": {"tool": "check_coverage", "key": "coverage_active", "value": True}}
        )
        assert fn(valid_claims_execution)
        assert "check_coverage.coverage_active" in desc

        fn2, _ = _build_condition(
            {"tool_result_matches": {"tool": "check_coverage", "key": "coverage_active", "value": False}}
        )
        assert not fn2(valid_claims_execution)

    def test_tool_result_matches_missing_tool_is_false(self, invalid_claims_execution):
        """The lazy execution never called check_coverage -- condition must not fire."""
        fn, _ = _build_condition(
            {"tool_result_matches": {"tool": "check_coverage", "key": "coverage_active", "value": True}}
        )
        assert not fn(invalid_claims_execution)

    def test_multiple_conditions_and_together(self, valid_claims_execution):
        fn, _ = _build_condition(
            {"input_matches": "pharmacy", "step_present": "lookup_formulary"}
        )
        assert fn(valid_claims_execution)
        fn2, _ = _build_condition(
            {"input_matches": "pharmacy", "step_present": "escalate"}
        )
        assert not fn2(valid_claims_execution)

    def test_unknown_condition_type_raises(self):
        with pytest.raises(ValueError, match="Unknown condition"):
            _build_condition({"vibe_check": True})


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


BRANCHING_CONTRACT = """
name: branching-v1
version: "1.0.0"
constraints:
  - type: must_not_use_only_parametric_knowledge

  - type: must_include_steps
    steps: ["check_coverage"]

  # Formulary work is only required when coverage is active
  - type: must_include_steps
    steps: ["lookup_formulary"]
    when:
      tool_result_matches:
        tool: check_coverage
        key: coverage_active
        value: true

  # On the escalation path the agent must not render a decision
  - type: must_not_include_steps
    steps: ["render_decision"]
    when:
      step_present: "flag_for_human_review"

  - type: must_contain_citations
    min_count: 1
    severity: warning
"""


class TestYamlConditions:
    def test_when_wraps_constraint_as_conditional(self, tmp_path):
        contract, _ = load_contract_from_yaml(write_contract(tmp_path, BRANCHING_CONTRACT))
        conditionals = [c for c in contract.constraints if isinstance(c, ConditionalConstraint)]
        assert len(conditionals) == 2
        assert any(isinstance(c.inner, MustNotIncludeSteps) for c in conditionals)

    def test_condition_fires_on_active_coverage(self, tmp_path, valid_claims_execution):
        contract, _ = load_contract_from_yaml(write_contract(tmp_path, BRANCHING_CONTRACT))
        verdict = validate(contract, valid_claims_execution)
        # Active coverage -> formulary constraint fires -> present -> PASS.
        # Escalation path constraint skips (no flag_for_human_review step).
        assert verdict.status == VerdictStatus.PASS
        assert verdict.checks_passed == verdict.checks_performed == 5

    def test_condition_skips_on_missing_tool(self, tmp_path, invalid_claims_execution):
        contract, _ = load_contract_from_yaml(write_contract(tmp_path, BRANCHING_CONTRACT))
        verdict = validate(contract, invalid_claims_execution)
        # No check_coverage call -> formulary conditional SKIPS -- but the
        # unconditional core still fails (parametric-only, missing step).
        assert verdict.status == VerdictStatus.FAIL
        failed_names = {v.constraint_name for v in verdict.violations}
        assert "must_not_use_only_parametric_knowledge" in failed_names
        assert not any("lookup_formulary" in n for n in failed_names)

    def test_severity_warning_produces_warn_not_fail(self, tmp_path, valid_claims_execution):
        yaml_body = """
name: warn-only-v1
version: "1.0.0"
constraints:
  - type: must_contain_citations
    min_count: 99
    severity: warning
"""
        contract, _ = load_contract_from_yaml(write_contract(tmp_path, yaml_body))
        verdict = validate(contract, valid_claims_execution)
        assert verdict.status == VerdictStatus.WARN

    def test_unknown_constraint_type_raises(self, tmp_path):
        yaml_body = """
name: bad-v1
constraints:
  - type: must_do_the_right_thing
"""
        with pytest.raises(ValueError, match="Unknown constraint type"):
            load_contract_from_yaml(write_contract(tmp_path, yaml_body))
