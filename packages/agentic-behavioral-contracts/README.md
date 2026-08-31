# agentic-behavioral-contracts

**Behavioral validation for AI agents: check whether the agent followed the correct process, not just whether it produced a correct-looking output.**

```bash
pip install agentic-behavioral-contracts
```

## The problem

AI agents in regulated domains — claims processing, KYC/AML, clinical decision support — make decisions that matter. An agent that approves a claim from its own training knowledge, without checking the formulary database, can produce a fluent, plausible, *correct-looking* answer with a fabricated policy citation. Output-quality evaluation scores it well. An auditor scores it as a violation.

Observability tools show *what happened*. Output evals score *what was said*. This library validates *what was done*: which data sources were consulted, which steps ran, in what order, and whether the output carries required evidence — deterministically, from the OpenTelemetry traces your agent already emits, with no changes to agent code.

## Quickstart

Define what correct behavior looks like as a contract, then validate any execution's trace against it:

```yaml
# claims_contract.yaml
name: claims-processing-v1
version: "1.0.0"

# Map tool names (gen_ai.tool.name spans) to the data sources they represent
source_map:
  lookup_formulary:
    source_name: formulary-db
    source_type: database
  check_coverage:
    source_name: coverage-policy-api
    source_type: api

constraints:
  - type: must_not_use_only_parametric_knowledge
  - type: must_retrieve_from
    sources: ["formulary-db", "coverage-policy-api"]
  - type: must_include_steps
    steps: ["lookup_formulary", "check_coverage", "render_decision"]
  - type: must_precede
    before: check_coverage
    after: render_decision
  - type: must_contain_citations
    min_count: 1
```

```python
from agent_validator import validate, create_audit_record, render_audit_report
from agent_validator.adapters.otel import OTELAdapter
from agent_validator.generate import load_contract_from_yaml

contract, source_map = load_contract_from_yaml("claims_contract.yaml")
adapter = OTELAdapter(tool_source_map=source_map)

execution = adapter.normalize(otel_trace_json)   # OTLP JSON export dict
verdict = validate(contract, execution)

print(verdict.status)          # PASS | FAIL | WARN
for v in verdict.violations:   # each with message + evidence
    print(v.constraint_name, "-", v.message)

record = create_audit_record(verdict, execution, contract.version)
print(render_audit_report(record))
```

Or from the command line:

```bash
agent-validate run --contract claims_contract.yaml --traces "traces/*.json" --fail-on-violation
```

## Constraint types

| Constraint | Validates |
|---|---|
| `must_retrieve_from` | Each named data source was consulted (via `source_map`) |
| `must_not_use_only_parametric_knowledge` | At least one tool call or retrieval happened — the agent didn't answer purely from training data |
| `must_include_steps` | Every named step appears in the execution |
| `must_not_include_steps` | None of the named steps appear (branch-specific prohibitions) |
| `must_precede` | Step A ran before step B |
| `must_contain_citations` | The output contains at least N citation references (Section 4.2.1, [1], 31 CFR 1010.230, Art. 28, ...) |
| `must_escalate_when` | When a condition holds, an escalation/human-review step must be present (Python API) |

Every constraint accepts `severity: error` (default, produces FAIL) or `severity: warning` (produces WARN).

## Multiple valid execution paths

Real agents have more than one legitimate path. A member with expired coverage should be denied *without* a formulary lookup — a contract that hard-requires the lookup false-alarms on every legitimate fast deny. Gate constraints with `when:` so they only evaluate when the condition holds:

```yaml
constraints:
  # Unconditional core: holds on EVERY valid path
  - type: must_include_steps
    steps: ["check_coverage", "render_decision"]

  # Only required when coverage is active
  - type: must_include_steps
    steps: ["lookup_formulary"]
    when:
      tool_result_matches:
        tool: check_coverage
        key: coverage_active
        value: true
```

Condition types (AND-ed when combined): `tool_result_matches` (a tool's parsed output contains key == value), `input_matches` (case-insensitive regex on the request), `step_present` (a step appears in the execution), `metadata` (execution metadata match).

Two rules keep branching contracts honest:

1. **Gate on facts the agent doesn't control** — the request, or committed tool results. Never on whether the agent felt like doing a step, or a lazy agent selects its own requirements.
2. **Keep a strong unconditional core.** An agent that skips the fact-producing step dodges the gated constraints — and is caught by the core.

The Python API offers the same via `when(condition, constraint)` with arbitrary callables, plus `must_escalate_when` for escalation rules.

## Generate contracts from a golden trace

Run your agent once on a known-good case and generate a baseline contract from what it did:

```bash
agent-validate generate --traces golden_trace.json --name my-agent-v1 --output contract.yaml
```

Every data source consulted becomes `must_retrieve_from`, every tool call a required step, the observed ordering a `must_precede` chain, citations in the output a citation requirement. Review the result — you decide which constraints generalize beyond the one golden case.

## Continuous monitoring

Validate every execution as traces arrive, from a directory or from AWS CloudWatch (`pip install agentic-behavioral-contracts[cloudwatch]`):

```python
from agent_validator import monitor_directory, monitor_cloudwatch

stats = monitor_directory(
    contract=contract,
    adapter=adapter,
    watch_dir="./incoming_traces",
    output_dir="./audit_records",
    on_violation=lambda record: alert(record),
)
# stats.compliance_rate, stats.passed, stats.failed, ...
```

## Audit records

Every validation can produce a structured, serializable audit record: the verdict, per-constraint evidence (what was required, what was found, what was missing), contract version, and an execution summary. Stored as JSON, these are the continuous, per-execution evidence trail that compliance reviews ask for — not a trace visualization, a verdict with proof.

## Framework support

Works with any agent framework that emits OpenTelemetry spans following the GenAI semantic conventions (`gen_ai.operation.name`, `gen_ai.tool.name`, ...). Validated against Strands Agents, LangChain/LangGraph, PydanticAI, and Claude Agent SDK. Trace parsing is provided by [agentic-otel](https://pypi.org/project/agentic-otel/), which auto-detects the framework and absorbs format differences.

Domain contract templates are included for claims processing, KYC/AML, and clinical decision support (`agent-validate list-contracts`).

## What this is not

- **Not a guardrail.** Contracts validate complete executions after the fact; positive constraints ("must include step X") cannot be checked until the execution finishes. Use runtime guardrails for I/O filtering; use this for process validation and audit evidence.
- **Not an output-quality eval.** It will not tell you whether the answer was helpful — it tells you whether the answer was produced the right way. Run both: they catch disjoint failure classes.

## Support and stability

This is a community open source project, not an AWS service or product.

- **Support:** community only, via GitHub issues. It is not covered by AWS Support plans, and there is no SLA.
- **Stability:** pre-1.0 and published with the `Development Status :: 4 - Beta` classifier. The API may change between minor versions; pin a version if you depend on it.
- **Warranty:** provided "AS IS", without warranties or conditions of any kind, as stated in the [Apache License 2.0](LICENSE) (Sections 7 and 8).

You are responsible for evaluating whether it fits your own compliance and operational requirements before relying on it.

## License

Apache-2.0
