# Code Review Criteria

This document defines the standards for code review in this project.

## Contents

| Section                  | What it covers                                    |
|--------------------------|---------------------------------------------------|
| Design Principles        | DRY, SoC, SOLID                                   |
| Source File Standards    | Docstrings, type hints, async patterns            |
| Test File Standards      | Table-driven tests, coverage requirements         |
| Error Handling           | Consistent patterns, meaningful messages          |
| Naming Conventions       | Clear, descriptive, consistent                    |

---

## Design Principles

### DRY (Don't Repeat Yourself)

- **Extract shared logic** - If code appears 3+ times, extract to a function/class
- **Avoid copy-paste** - Duplicated code diverges over time and causes bugs
- **Use inheritance/composition** - For shared behavior across similar classes
- **Centralize constants** - Define once in `const.py`, import everywhere

```python
# BAD - duplicated validation logic
def validate_host(host):
    if not host or len(host) < 1:
        raise ValueError("Invalid host")

def validate_url(url):
    if not url or len(url) < 1:  # Same pattern!
        raise ValueError("Invalid url")

# GOOD - extracted to reusable function
def validate_non_empty(value: str, name: str) -> None:
    if not value or len(value) < 1:
        raise ValueError(f"Invalid {name}")
```

### Separation of Concerns (SoC)

- **Single responsibility** - Each module/class does one thing well
- **Clear module boundaries** - Don't mix I/O, parsing, and business logic
- **Layered architecture** - UI → Service → Data layers don't skip levels

```text
# Project layers (don't skip levels)
┌─────────────────────────────────────┐
│  Home Assistant Integration Layer   │  ← config_flow.py, sensor.py
├─────────────────────────────────────┤
│  Core Business Logic                │  ← discovery/, auth/, parsers/
├─────────────────────────────────────┤
│  Data/I/O Layer                     │  ← modem_config/, network.py
└─────────────────────────────────────┘
```

### SOLID Principles (where applicable)

- **S - Single Responsibility** - A class should have one reason to change
- **O - Open/Closed** - Open for extension, closed for modification (use ABCs)
- **L - Liskov Substitution** - Subtypes must be substitutable for base types
- **I - Interface Segregation** - Prefer small, focused interfaces
- **D - Dependency Inversion** - Depend on abstractions, not concretions

Most relevant to this project:

- **SRP**: Parsers only parse, auth strategies only authenticate
- **OCP**: New modems added via new parser files, not modifying existing code
- **DIP**: Core code depends on `ModemParser` ABC, not concrete parsers

---

## Source File Standards

### Module Docstring (required)

Every Python file must have a module docstring at the top:

```python
"""Short one-line summary of what this module does.

Longer description if needed, explaining:
- Purpose and responsibility
- Key classes/functions provided
- Usage examples

Architecture:
    Optional ASCII diagram showing relationships

Example:
    >>> from module import function
    >>> function("input")
    "output"
"""
```

### Public API Docstrings

All public functions and classes must have docstrings:

```python
def process_data(raw: str, validate: bool = True) -> dict[str, Any]:
    """Process raw modem data into structured format.

    Args:
        raw: Raw HTML or JSON string from modem
        validate: Whether to validate the output schema

    Returns:
        Parsed data dictionary with keys: downstream, upstream, system_info

    Raises:
        ParseError: If raw data cannot be parsed
        ValidationError: If validate=True and output fails schema check
    """
```

### Type Hints (required)

All function signatures must have type hints:

```python
# BAD
def get_parser(name):
    ...

# GOOD
def get_parser(name: str) -> type[ModemParser] | None:
    ...
```

### No Blocking I/O in Async Context

When calling sync functions from async code (e.g., in `config_flow.py`,
`__init__.py`), check whether the function does I/O — file reads,
network calls, subprocess. If yes, wrap the call in an executor:

```python
# BAD - blocks event loop
adapter = get_auth_adapter_for_parser(parser_name)  # reads YAML files

# GOOD - runs in thread pool
adapter = await hass.async_add_executor_job(get_auth_adapter_for_parser, parser_name)
```

Home Assistant warns at runtime ("Detected blocking call…") but
catching this during development is better — Ruff can't detect it
when the blocking call is nested inside another function.

### Loading HAR Fixtures

Always use `load_har_json()` from
`solentlabs.cable_modem_monitor_core.har` for HAR file reads:

```python
from solentlabs.cable_modem_monitor_core.har import load_har_json

har_data = load_har_json(path)
```

Never use raw `json.loads(path.read_text())` for HAR files — they're
stored in Git LFS and the shared loader detects LFS pointers, attempts
`git lfs pull` automatically, and produces actionable guidance instead
of an opaque `JSONDecodeError` when LFS isn't set up. The only
exception is standalone scripts that intentionally avoid Core as a
dependency (e.g., `check_fixture_pii.py`), which inline the LFS-pointer
check themselves.

### Corresponding Test File

Every source file should have a corresponding test file:

```text
# Core package
packages/cable_modem_monitor_core/.../auth/form.py
    → packages/cable_modem_monitor_core/tests/auth/test_form.py

# Catalog package
packages/cable_modem_monitor_catalog/.../registry.py
    → packages/cable_modem_monitor_catalog/tests/test_registry.py

# HA adapter
custom_components/cable_modem_monitor/services.py
    → tests/components/test_services.py
```

---

## Test File Standards

### Module Docstring with TEST DATA TABLES

```python
"""Tests for auth discovery module.

TEST DATA TABLES
================
This module uses table-driven tests. Tables are defined at the top
of the file with ASCII box-drawing comments for readability.
"""
```

### Tables at TOP of File

Define all test data tables immediately after imports:

```python
# =============================================================================
# Test Data Tables
# =============================================================================

# ┌─────────────┬──────────────┬─────────────────────────────┐
# │ input       │ expected     │ description                 │
# ├─────────────┼──────────────┼─────────────────────────────┤
# │ "valid"     │ True         │ normal case                 │
# │ ""          │ False        │ empty string rejected       │
# └─────────────┴──────────────┴─────────────────────────────┘
#
# fmt: off
VALIDATION_CASES = [
    # (input,    expected, description)
    ("valid",    True,     "normal case"),
    ("",         False,    "empty string rejected"),
]
# fmt: on
```

### Use `# fmt: off/on` Guards

Preserve column alignment in tables:

```python
# fmt: off
CASES = [
    ("short",      1,    "x"),
    ("longer",     100,  "y"),
    ("very long",  1000, "z"),
]
# fmt: on
```

### Consume Tables with `@pytest.mark.parametrize`

```python
@pytest.mark.parametrize(
    "input,expected,desc",
    VALIDATION_CASES,
    ids=[c[2] for c in VALIDATION_CASES],  # Use description as test ID
)
def test_validation(input: str, expected: bool, desc: str):
    """Test validation via table-driven cases."""
    result = validate(input)
    assert result == expected, f"Failed: {desc}"
```

### Coverage Requirements

- **Core components**: Target 100% where sensible
- **Parsers**: Focus on parse logic, not every edge case
- **Integration tests**: Cover happy path + critical error paths

---

## Error Handling

### Consistent Exception Types

Define exceptions alongside the code that raises them. Each module
owns its own error types:

```python
# In loaders/http.py
class ResourceLoadError(Exception): ...
class LoginPageDetectedError(ResourceLoadError): ...

# In orchestration/collector.py
class LoginLockoutError(Exception): ...
```

### Meaningful Error Messages

Include context in error messages:

```python
# BAD
raise ValueError("Invalid input")

# GOOD
raise ValueError(f"Invalid host '{host}': must be IP address or hostname")
```

### Modem-Specific Log Messages: `[MODEL]` Tag

Runtime log messages for a specific modem include the model name as a
`[MODEL]` tag at the end of the subject phrase, before the separator
(`:` or `—`):

```python
_logger.info("Parse complete [%s]: %d DS, %d US", model, ds, us)
_logger.debug("Fetched /path [%s]: 200 (1234 bytes)", model)
```

Auth success logging belongs in the **collector**, not in individual
auth managers — the collector has the model name and logs the
`AuthResult` centrally.

### Log Before Raising

Log errors at appropriate level before raising:

```python
_LOGGER.error("Authentication failed for %s: %s", host, error)
raise AuthenticationError(f"Failed to authenticate with {host}") from error
```

---

## Naming Conventions

### Files and Modules

- **snake_case** for all Python files: `auth_discovery.py`, `config_flow.py`
- **Descriptive names**: `parser_discovery.py` not `pd.py`

### Classes

- **PascalCase**: `ModemParser`, `AuthStrategy`, `DiscoveryPipeline`
- **Suffix with type**: `ArrisSB8200Parser`, `FormPlainAuthStrategy`

### Functions and Variables

- **snake_case**: `get_parser_by_name()`, `working_url`
- **Verb prefixes for functions**: `get_`, `create_`, `validate_`, `parse_`
- **Boolean prefixes**: `is_`, `has_`, `can_`, `should_`

### Constants

- **SCREAMING_SNAKE_CASE**: `DEFAULT_TIMEOUT`, `MAX_RETRIES`
- **Define in `const.py`** for shared constants

### Private Members

- **Single underscore prefix**: `_internal_method()`, `_CACHE`
- **Avoid double underscore** unless name mangling is specifically needed

---

## Quick Checklist

### Source File Review

- [ ] Module docstring present
- [ ] Public functions/classes have docstrings
- [ ] Type hints on all signatures
- [ ] No blocking I/O in async context
- [ ] DRY - no duplicated code blocks
- [ ] SoC - single responsibility
- [ ] Test file exists

### Test File Review

- [ ] Module docstring with TEST DATA TABLES section
- [ ] Tables at TOP with ASCII box-drawing
- [ ] `# fmt: off/on` guards around tables
- [ ] `@pytest.mark.parametrize` consumes tables
- [ ] Descriptive test IDs from table
