# Catalog Documentation

This package contains modem configurations (modem.yaml), parser overrides
(parser.py), and test resources (HAR captures, golden files). It has no
business logic.

For architecture, specs, and field definitions, see the
[Core documentation](../../cable_modem_monitor_core/docs/).

| Document | Covers |
|----------|--------|
| [INTAKE_PIPELINE.md](INTAKE_PIPELINE.md) | Pipeline overview — who does what, extension points, fleet patterns |
| [MODEM_INTAKE_WORKFLOW.md](MODEM_INTAKE_WORKFLOW.md) | Operator workflow — step-by-step instructions with code snippets |
| [MOCK_SERVER.md](MOCK_SERVER.md) | Mock server for testing catalog entries |

**Note:** `FIELD_REGISTRY.md` and `VERIFICATION_STATUS.md` have moved to
[Core docs](../../cable_modem_monitor_core/docs/) — they define contracts
owned by the core package.
