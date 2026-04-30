"""Generic contract tests for every modem's parser.py PostProcessor.

The Core parsing pipeline calls a fixed set of methods on each
modem's optional ``PostProcessor`` class:

    parse_downstream(channels: list, resources: dict) -> list
    parse_upstream(channels: list, resources: dict)   -> list
    parse_system_info(system_info: dict, resources: dict) -> dict

This file dynamically discovers every ``parser.py`` under the catalog
and asserts each PostProcessor honors that contract — empty inputs
don't crash and methods return the right type. Adding a new
``parser.py`` automatically adds it to this test surface; contributors
never write per-modem tests.

Firmware-specific filter logic *inside* a method (e.g., a state
filter that drops non-OPERATE channels) is intentionally outside this
contract. Those branches are tested only when a real HAR fixture
naturally exercises them.
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_core.post_processor import load_post_processor


def _discover_post_processors() -> list[tuple[str, Any]]:
    """Walk the catalog tree, return (modem_id, PostProcessor instance) for each parser.py."""
    discovered: list[tuple[str, Any]] = []
    for parser_py in sorted(CATALOG_PATH.glob("*/*/parser.py")):
        modem_id = f"{parser_py.parent.parent.name}/{parser_py.parent.name}"
        pp = load_post_processor(parser_py)
        if pp is not None:
            discovered.append((modem_id, pp))
    return discovered


_POST_PROCESSORS = _discover_post_processors()

# Methods on the PostProcessor contract. Each row is the method name
# plus a degenerate (empty) input pair and the expected output type.
#
# fmt: off
_CONTRACT_METHODS: list[tuple[str, tuple[Any, ...], type]] = [
    ("parse_downstream",  ([], {}), list),
    ("parse_upstream",    ([], {}), list),
    ("parse_system_info", ({}, {}), dict),
]
# fmt: on


@pytest.mark.skipif(not _POST_PROCESSORS, reason="No parser.py files in catalog")
@pytest.mark.parametrize(
    "modem_id,pp",
    _POST_PROCESSORS,
    ids=[mid for mid, _ in _POST_PROCESSORS],
)
class TestPostProcessorContract:
    """Every PostProcessor must honor the Core pipeline contract."""

    @pytest.mark.parametrize(
        "method_name,empty_args,expected_type",
        _CONTRACT_METHODS,
        ids=[m[0] for m in _CONTRACT_METHODS],
    )
    def test_empty_inputs_return_correct_type(
        self,
        modem_id: str,
        pp: Any,
        method_name: str,
        empty_args: tuple[Any, ...],
        expected_type: type,
    ) -> None:
        """Each defined contract method returns its declared type for empty inputs."""
        method = getattr(pp, method_name, None)
        if method is None:
            pytest.skip(f"{modem_id} does not implement {method_name}")
        result = method(*empty_args)
        assert isinstance(result, expected_type), (
            f"{modem_id}.{method_name}{empty_args} returned "
            f"{type(result).__name__}, expected {expected_type.__name__}"
        )

    def test_unknown_resource_keys_do_not_crash(self, modem_id: str, pp: Any) -> None:
        """Unexpected resource entries don't crash any contract method.

        Defensive against firmware drift — a future firmware revision may
        add or remove endpoints; the post-processor must not raise.
        """
        garbage_resources: dict[str, Any] = {
            "/unexpected/endpoint": {"nodes": []},
            "/another/unknown": None,
            "/garbage": "not even a dict",
        }
        for method_name, empty_args, _ in _CONTRACT_METHODS:
            method = getattr(pp, method_name, None)
            if method is None:
                continue
            # Replace the resources arg (always last) with garbage.
            args = (*empty_args[:-1], garbage_resources)
            method(*args)
