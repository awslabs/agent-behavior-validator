# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end demo: validate KYC/AML agent behavior against behavioral contracts.

Usage:
    # Low-risk customer, full process — PASS
    python -m examples.kyc_aml_agent.run --traces examples/sample_traces/kyc_valid.json

    # High-risk customer, auto-cleared without sanctions check — FAIL
    python -m examples.kyc_aml_agent.run --traces examples/sample_traces/kyc_invalid.json

    # High-risk customer needing escalation
    python -m examples.kyc_aml_agent.run --traces examples/sample_traces/kyc_valid.json --risk-score 85
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from agent_validator.adapters.otel import OTELAdapter
from agent_validator.audit import create_audit_record, render_audit_report
from agent_validator.contracts.templates.kyc_aml import kyc_aml_contract
from agent_validator.validator import validate

TOOL_SOURCE_MAP = {
    "screen_sanctions": {"source_name": "sanctions-db", "source_type": "database"},
    "verify_jurisdiction": {"source_name": "jurisdiction-rules", "source_type": "database"},
    "assess_risk": {"source_name": "risk-model", "source_type": "api"},
}


def run_with_traces(trace_path: str, risk_score: int | None = None) -> None:
    """Load pre-captured OTEL traces and validate against the KYC/AML contract."""
    with open(trace_path) as f:
        raw_trace = json.load(f)

    adapter = OTELAdapter(tool_source_map=TOOL_SOURCE_MAP)
    execution = adapter.normalize(raw_trace)

    if risk_score is not None:
        execution.metadata["risk_score"] = risk_score

    verdict = validate(kyc_aml_contract, execution)
    record = create_audit_record(verdict, execution, kyc_aml_contract.version)

    print(render_audit_report(record))
    print()
    print("--- JSON Audit Record ---")
    print(json.dumps(record.to_dict(), indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate KYC/AML agent behavior against behavioral contracts"
    )
    parser.add_argument("--traces", type=str, required=True, help="Path to OTEL trace JSON file")
    parser.add_argument(
        "--risk-score",
        type=int,
        default=None,
        help="Override the customer risk score (triggers escalation constraint at >= 70)",
    )
    args = parser.parse_args()
    run_with_traces(args.traces, risk_score=args.risk_score)


if __name__ == "__main__":
    main()
