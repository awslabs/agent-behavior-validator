# Security Policy

## Reporting a vulnerability

If you discover a potential security issue in this project, please notify
AWS/Amazon Security via our
[vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/)
or directly to [aws-security@amazon.com](mailto:aws-security@amazon.com).

**Please do not create a public GitHub issue for security reports.**

## Supported versions

This is a pre-1.0 community project. Security fixes are applied to the
latest released version of each package. There are no long-term support
branches.

| Package | Supported |
|---|---|
| `agentic-behavioral-contracts` | latest release |
| `agentic-otel` | latest release |

## Scope notes

Both packages are client-side libraries with no network listener, no
credential handling, and no hosted component. They parse trace data supplied
by the caller and run entirely within the caller's environment.

Trace content is treated strictly as data: parsing only, with no `eval`,
no code deserialization, and no subprocess execution. Contract files in YAML
are loaded with `yaml.safe_load`. Note that contract files supplied as Python
modules execute by design and carry the same trust level as the application
embedding the library — supply them only from sources you control.
