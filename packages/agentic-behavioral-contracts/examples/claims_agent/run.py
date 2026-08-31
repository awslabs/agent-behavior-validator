# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end demo: validate claims agent behavior against behavioral contracts.

Usage:
    # With pre-captured traces (no AWS needed):
    python -m examples.claims_agent.run --traces examples/sample_traces/valid_claim.json
    python -m examples.claims_agent.run --traces examples/sample_traces/invalid_claim.json

    # With live agent (requires AWS credentials + Bedrock access):
    python -m examples.claims_agent.run --live --claim "Process pharmacy claim for member MEM-001, drug lisinopril"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from agent_validator.adapters.otel import OTELAdapter
from agent_validator.audit import create_audit_record, render_audit_report
from agent_validator.contracts.templates.claims_processing import claims_processing_contract
from agent_validator.validator import validate

# Standard tool-to-source mapping for the claims processing agent
TOOL_SOURCE_MAP = {
    "lookup_formulary": {"source_name": "formulary-db", "source_type": "database"},
    "check_coverage": {"source_name": "coverage-policy", "source_type": "api"},
}


def run_with_traces(trace_path: str, claim_type: str = "pharmacy") -> None:
    """Load pre-captured OTEL traces and validate against the claims contract."""
    with open(trace_path) as f:
        raw_trace = json.load(f)

    adapter = OTELAdapter(tool_source_map=TOOL_SOURCE_MAP)
    execution = adapter.normalize(raw_trace)

    # Set claim_type metadata for escalation constraint
    execution.metadata["claim_type"] = claim_type

    verdict = validate(claims_processing_contract, execution)
    record = create_audit_record(
        verdict, execution, claims_processing_contract.version
    )

    print(render_audit_report(record))
    print()
    print("--- JSON Audit Record ---")
    print(json.dumps(record.to_dict(), indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate claims agent behavior against behavioral contracts"
    )
    parser.add_argument(
        "--traces",
        type=str,
        help="Path to a pre-captured OTEL trace JSON file",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run a live Strands agent (requires AWS credentials)",
    )
    parser.add_argument(
        "--claim",
        type=str,
        default="Process pharmacy claim for member MEM-001, drug lisinopril",
        help="Claim text to process (used with --live)",
    )
    parser.add_argument(
        "--claim-type",
        type=str,
        default="pharmacy",
        help="Claim type for escalation checking (e.g., pharmacy, medical, chiropractic)",
    )

    args = parser.parse_args()

    if args.traces:
        run_with_traces(args.traces, claim_type=args.claim_type)
    elif args.live:
        print("Live agent mode requires Strands Agents + Bedrock.")
        print("This mode is not yet implemented in the MVP.")
        print("Use --traces with sample trace files instead.")
        sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
