# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the core validation engine."""

from agent_validator.contracts.templates.claims_processing import claims_processing_contract
from agent_validator.models import VerdictStatus
from agent_validator.validator import validate
from agent_validator.audit import create_audit_record, render_audit_report


def test_valid_execution_passes(valid_claims_execution):
    verdict = validate(claims_processing_contract, valid_claims_execution)
    assert verdict.status == VerdictStatus.PASS
    assert verdict.violations == []
    assert verdict.checks_performed == 6
    assert verdict.checks_passed == 6


def test_invalid_execution_fails(invalid_claims_execution):
    verdict = validate(claims_processing_contract, invalid_claims_execution)
    assert verdict.status == VerdictStatus.FAIL
    assert len(verdict.violations) > 0
    violation_names = [v.constraint_name for v in verdict.violations]
    assert any("must_retrieve_from" in n for n in violation_names)
    assert any("parametric" in n for n in violation_names)
    assert any("must_include_steps" in n for n in violation_names)


def test_escalation_needed_fails(escalation_needed_execution):
    verdict = validate(claims_processing_contract, escalation_needed_execution)
    assert verdict.status == VerdictStatus.FAIL
    violation_names = [v.constraint_name for v in verdict.violations]
    assert any("escalate" in n for n in violation_names)


def test_audit_record_generation(valid_claims_execution):
    verdict = validate(claims_processing_contract, valid_claims_execution)
    record = create_audit_record(verdict, valid_claims_execution, "1.0.0")
    assert record.audit_id is not None
    assert record.verdict.status == VerdictStatus.PASS
    assert record.execution_summary["step_count"] == 5
    assert "formulary-db" in record.execution_summary["data_sources_consulted"]


def test_audit_record_to_dict(valid_claims_execution):
    verdict = validate(claims_processing_contract, valid_claims_execution)
    record = create_audit_record(verdict, valid_claims_execution, "1.0.0")
    d = record.to_dict()
    assert d["verdict"]["status"] == "pass"
    assert d["contract_version"] == "1.0.0"
    assert "audit_id" in d


def test_audit_report_rendering(invalid_claims_execution):
    verdict = validate(claims_processing_contract, invalid_claims_execution)
    record = create_audit_record(verdict, invalid_claims_execution, "1.0.0")
    report = render_audit_report(record)
    assert "FAIL" in report
    assert "VIOLATIONS" in report
    assert "AUDIT RECORD" in report
