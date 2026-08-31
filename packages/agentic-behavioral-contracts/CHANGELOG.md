# Changelog

## 0.2.0 (unreleased)

### Added

- **Conditional constraints in YAML contracts** — any constraint can carry a
  `when:` block so that it only evaluates when the condition holds. This is
  how one contract validates multiple legitimate execution paths. Condition
  types (AND-ed when combined):
  - `tool_result_matches`: a tool was called and its parsed output contains a
    key/value match
  - `input_matches`: case-insensitive regex on the execution input text
  - `step_present`: a named step (or any of a list) appears in the execution
  - `metadata`: execution metadata key-values all match
- **`must_not_include_steps` constraint** — the negative counterpart of
  `must_include_steps`, for branch-specific prohibitions (e.g. "on the
  escalation path, the agent must not render a decision").
- **`severity` field in YAML constraints** — `error` (default) or `warning`;
  warnings produce a WARN verdict instead of FAIL.
- YAML loader now fails fast on unknown constraint types and condition types
  instead of silently skipping them.
- `boto3` documented as the optional `cloudwatch` extra for
  `monitor_cloudwatch`.

### Changed

- **OTEL parsing is now provided by the `agentic-otel` package** (new
  dependency). The adapter behavior is unchanged; the parsing internals moved
  to a shared, separately-tested library.
- **`pyyaml` is now a core dependency** (was the optional `yaml` extra):
  YAML contracts are the primary interface.
- Slimmer source distribution: development documents are no longer packaged.

## 0.1.0 (2026-03-26)

Initial release: contract engine with six constraint types, OTEL adapter,
YAML contract loading and generation from golden traces, CLI
(`agent-validate`), audit records, continuous monitoring (CloudWatch and
directory sources), compliance drift tracking, and domain templates for
claims processing, KYC/AML, and clinical decision support.
