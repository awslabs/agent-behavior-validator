# Agent Behavior Validator

Validate what your AI agents actually **did**, not just what they said.

Output-quality evaluation scores the answer. This validates the *process*:
which data sources the agent consulted, which steps it executed and in what
order, whether it escalated when required, and whether its output carries
required evidence. It reads the OpenTelemetry traces your agents already
emit — no changes to agent code — and produces audit-ready evidence records
for every validated execution.

The failure it exists to catch: an agent that answers a question correctly
and fluently, with a plausible-looking citation, **without ever consulting
the required data source**. That execution passes output evaluation and
fails an audit.

## Packages

| Package | Install | What it does |
|---|---|---|
| [agentic-behavioral-contracts](packages/agentic-behavioral-contracts) | `pip install agentic-behavioral-contracts` | The contract engine: declarative YAML contracts with deterministic constraint types, conditional constraints for agents with multiple legitimate execution paths, contract auto-generation from known-good traces, a CLI, continuous monitoring, and audit record generation. |
| [agentic-otel](packages/agentic-otel) | `pip install agentic-otel` | Zero-dependency normalization layer for OpenTelemetry GenAI agent traces: single-pass parsing, span classification with confidence scores, and framework detection. |

## Quick look

```yaml
# claims_contract.yaml
name: claims-processing-v1
source_map:
  lookup_formulary: { source_name: formulary-db,        source_type: database }
  check_coverage:   { source_name: coverage-policy-api, source_type: api }
constraints:
  - type: must_not_use_only_parametric_knowledge
  - type: must_retrieve_from
    sources: ["coverage-policy-api"]
  - type: must_include_steps
    steps: ["check_coverage", "render_decision"]
  - type: must_precede
    before: check_coverage
    after: render_decision
```

```python
from agent_validator import validate
from agent_validator.generate import load_contract_from_yaml

contract, _ = load_contract_from_yaml("claims_contract.yaml")
verdict = validate(contract, execution)
print(verdict.status)   # PASS | FAIL | WARN
```

See each package's README for the full constraint reference, conditional
constraints, contract generation from golden traces, and continuous
monitoring.

## Framework support

Works with any agent framework that emits OpenTelemetry spans following the
GenAI semantic conventions. Validated against Strands Agents,
LangChain/LangGraph, PydanticAI, and the Claude Agent SDK — the same
contract runs unchanged across frameworks, because `agentic-otel` absorbs
the format differences.

## Support and stability

This is a community open source project, not an AWS service or product.

- **Support:** community only, via GitHub issues. Not covered by AWS Support plans; no SLA.
- **Stability:** pre-1.0, published with the `Development Status :: 4 - Beta` classifier. APIs may change between minor versions — pin a version if you depend on it.
- **Warranty:** provided "AS IS", without warranties or conditions of any kind, per the [Apache License 2.0](LICENSE) (Sections 7 and 8).

You are responsible for evaluating whether it fits your own compliance and
operational requirements before relying on it.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for
vulnerability reporting.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
