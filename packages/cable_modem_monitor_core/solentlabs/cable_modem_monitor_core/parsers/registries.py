"""Parser registries — type-to-callable dispatch tables.

Maps parser.yaml section config types to parser callables. Seven channel
format types and six system info source types are registered.

Channel parsers: ``(section, resources) -> list[dict]``
System info parsers: ``(source, resources) -> dict``

The ``CHANNEL_PARSERS`` and ``SYSINFO_PARSERS`` dicts derive from
the central format-model lists (``CHANNEL_SECTION_MODELS`` and
``SYSTEM_INFO_SOURCE_MODELS``) by joining each model with its wrapper
in the per-tag tables below. Adding a format means:

1. Define the model with its ``format_tag``/``decode_kind``/
   ``transports`` ClassVars and append it to the appropriate model
   list in ``models/parser_config/``.
2. Define the wrapper here and add an entry to
   ``_CHANNEL_WRAPPERS_BY_TAG`` (or the sysinfo equivalent).

See PARSING_SPEC.md Parser Registry section.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..models.parser_config.config import CHANNEL_SECTION_MODELS
from ..models.parser_config.javascript import JSEmbeddedSection
from ..models.parser_config.js_json import JSJsonSection
from ..models.parser_config.json_format import JSONSection
from ..models.parser_config.json_transposed import JSONTransposedSection
from ..models.parser_config.system_info import (
    SYSTEM_INFO_SOURCE_MODELS,
    HNAPSystemInfoSource,
    HTMLFieldsSource,
    JSONSystemInfoSource,
    JSSystemInfoSource,
    JSVarsSystemInfoSource,
    XMLSystemInfoSource,
)
from ..models.parser_config.table import HTMLTableSection
from ..models.parser_config.transposed import HTMLTableTransposedSection
from ..models.parser_config.xml_format import XMLSection
from .formats.hnap import HNAPParser
from .formats.hnap_fields import HNAPFieldsParser
from .formats.html_fields import HTMLFieldsParser
from .formats.html_table import HTMLTableParser
from .formats.html_table_transposed import HTMLTableTransposedParser
from .formats.js_embedded import JSEmbeddedParser
from .formats.js_json_parser import JSJsonParser
from .formats.js_system_info import JSSystemInfoParser
from .formats.js_vars import JSVarsParser
from .formats.json_parser import JSONParser
from .formats.json_system_info import JSONSystemInfoParser
from .formats.json_transposed import JSONTransposedParser
from .formats.xml_parser import XMLChannelParser
from .formats.xml_system_info import XMLSystemInfoParser

# ---------------------------------------------------------------------------
# Channel parser registry
# ---------------------------------------------------------------------------


def _parse_hnap_channels(
    section: Any,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from an HNAP section."""
    hnap_parser = HNAPParser(section)
    channels = hnap_parser.parse(resources)
    if not isinstance(channels, list):
        return []
    return channels


def _parse_html_table_channels(
    section: HTMLTableSection,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from HTML table section(s) with merge_by support."""
    primary_channels: list[dict[str, Any]] = []
    companion_tables: list[tuple[list[dict[str, Any]], list[str]]] = []

    for table_def in section.tables:
        parser = HTMLTableParser(section.resource, table_def)
        channels = parser.parse(resources)
        if not isinstance(channels, list):
            continue

        if table_def.merge_by is not None:
            companion_tables.append((channels, table_def.merge_by))
        else:
            primary_channels.extend(channels)

    for companion_channels, merge_by in companion_tables:
        _merge_channels(primary_channels, companion_channels, merge_by)

    # Auto-assign channel_number from 1-based row position when not
    # already mapped by parser.yaml.  See CHANNEL_IDENTIFICATION_SPEC §10.
    for idx, channel in enumerate(primary_channels, start=1):
        if "channel_number" not in channel:
            channel["channel_number"] = idx

    return primary_channels


def _parse_transposed_channels(
    section: HTMLTableTransposedSection,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from transposed HTML table section(s) with merge_by support."""
    # Normalize flat form to tables list
    if section.tables is not None:
        tables = section.tables
    else:
        from ..models.parser_config.transposed import TransposedTableDefinition

        assert section.selector is not None and section.rows is not None
        tables = [
            TransposedTableDefinition(
                selector=section.selector,
                rows=section.rows,
                channel_type=section.channel_type,
            )
        ]

    primary_channels: list[dict[str, Any]] = []
    companion_tables: list[tuple[list[dict[str, Any]], list[str]]] = []

    for table_def in tables:
        parser = HTMLTableTransposedParser(section.resource, table_def)
        channels = parser.parse(resources)
        if not isinstance(channels, list):
            continue

        if table_def.merge_by is not None:
            companion_tables.append((channels, table_def.merge_by))
        else:
            primary_channels.extend(channels)

    for companion_channels, merge_by in companion_tables:
        _merge_channels(primary_channels, companion_channels, merge_by)

    # Auto-assign channel_number from 1-based row position when not
    # already mapped by parser.yaml.  See CHANNEL_IDENTIFICATION_SPEC §10.
    for idx, channel in enumerate(primary_channels, start=1):
        if "channel_number" not in channel:
            channel["channel_number"] = idx

    return primary_channels


def _parse_js_embedded_channels(
    section: JSEmbeddedSection,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from JS-embedded section with unified channel_number.

    Concatenates function outputs in declaration order and assigns unified
    1-based ``channel_number`` across the combined list. Emits
    ``source_channel_number`` when the per-function position differs from
    the unified number.  See CHANNEL_IDENTIFICATION_SPEC §10.
    """
    function_results: list[list[dict[str, Any]]] = []
    for func in section.functions:
        parser = JSEmbeddedParser(section.resource, func)
        result = parser.parse(resources)
        if isinstance(result, list):
            function_results.append(result)

    channels: list[dict[str, Any]] = []
    unified = 1
    for func_channels in function_results:
        for func_pos, channel in enumerate(func_channels, start=1):
            channel["channel_number"] = unified
            if func_pos != unified:
                channel["source_channel_number"] = func_pos
            unified += 1
            channels.append(channel)

    return channels


def _parse_json_channels(
    section: JSONSection,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from a JSON API section."""
    parser = JSONParser(section)
    channels = parser.parse(resources)
    if not isinstance(channels, list):
        return []

    # Auto-assign channel_number from 1-based row position when not
    # already mapped by parser.yaml.  See CHANNEL_IDENTIFICATION_SPEC §10.
    for idx, channel in enumerate(channels, start=1):
        if "channel_number" not in channel:
            channel["channel_number"] = idx

    return channels


def _parse_js_json_channels(
    section: JSJsonSection,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from a js_json section — JSON arrays in JS variables."""
    parser = JSJsonParser(section)
    channels = parser.parse(resources)
    if not isinstance(channels, list):
        return []

    # Auto-assign channel_number from 1-based row position when not
    # already mapped by parser.yaml.  See CHANNEL_IDENTIFICATION_SPEC §10.
    for idx, channel in enumerate(channels, start=1):
        if "channel_number" not in channel:
            channel["channel_number"] = idx

    return channels


def _parse_xml_channels(
    section: XMLSection,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from an XML section."""
    parser = XMLChannelParser(section)
    channels = parser.parse(resources)
    if not isinstance(channels, list):
        return []

    # Auto-assign channel_number from 1-based row position when not
    # already mapped by parser.yaml.  See CHANNEL_IDENTIFICATION_SPEC §10.
    for idx, channel in enumerate(channels, start=1):
        if "channel_number" not in channel:
            channel["channel_number"] = idx

    return channels


def _parse_json_transposed_channels(
    section: JSONTransposedSection,
    resources: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse channels from a JSONTransposedParser section."""
    parser = JSONTransposedParser(section)
    channels = parser.parse(resources)
    if not isinstance(channels, list):
        return []

    # Auto-assign channel_number from 1-based row position when not
    # already mapped by parser.yaml.  See CHANNEL_IDENTIFICATION_SPEC §10.
    for idx, channel in enumerate(channels, start=1):
        if "channel_number" not in channel:
            channel["channel_number"] = idx

    return channels


# Wrappers keyed by format_tag. Combined with CHANNEL_SECTION_MODELS
# below to build CHANNEL_PARSERS — preserves locality (wrapper lives
# next to its peers) while removing the duplicated model→callable
# table.
_CHANNEL_WRAPPERS_BY_TAG: dict[str, Callable[..., list[dict[str, Any]]]] = {
    "table": _parse_html_table_channels,
    "table_transposed": _parse_transposed_channels,
    "javascript": _parse_js_embedded_channels,
    "javascript_json": _parse_js_json_channels,
    "hnap": _parse_hnap_channels,
    "json": _parse_json_channels,
    "json_transposed": _parse_json_transposed_channels,
    "xml": _parse_xml_channels,
}

# Maps section config type -> parser callable(section, resources) -> list[dict].
# Built by joining the central model list with the wrapper table — a
# missing wrapper for a registered model raises at import time.
CHANNEL_PARSERS: dict[type, Callable[..., list[dict[str, Any]]]] = {
    model: _CHANNEL_WRAPPERS_BY_TAG[model.format_tag] for model in CHANNEL_SECTION_MODELS
}


# ---------------------------------------------------------------------------
# System info source registry
# ---------------------------------------------------------------------------


def _parse_html_fields_sysinfo(
    source: HTMLFieldsSource,
    resources: dict[str, Any],
) -> dict[str, Any]:
    """Parse system_info from HTML label/value pairs."""
    html_si = HTMLFieldsParser(source)
    result = html_si.parse(resources)
    return result if isinstance(result, dict) else {}


def _parse_hnap_sysinfo(
    source: HNAPSystemInfoSource,
    resources: dict[str, Any],
) -> dict[str, Any]:
    """Parse system_info from HNAP response fields."""
    hnap_si = HNAPFieldsParser(source)
    result = hnap_si.parse(resources)
    return result if isinstance(result, dict) else {}


def _parse_js_sysinfo(
    source: JSSystemInfoSource,
    resources: dict[str, Any],
) -> dict[str, Any]:
    """Parse system_info from JS-embedded tagValueList variables."""
    js_si = JSSystemInfoParser(source)
    result = js_si.parse(resources)
    return result if isinstance(result, dict) else {}


def _parse_js_vars_sysinfo(
    source: JSVarsSystemInfoSource,
    resources: dict[str, Any],
) -> dict[str, Any]:
    """Parse system_info from JS variable assignments."""
    js_vars_si = JSVarsParser(source)
    result = js_vars_si.parse(resources)
    return result if isinstance(result, dict) else {}


def _parse_json_sysinfo(
    source: JSONSystemInfoSource,
    resources: dict[str, Any],
) -> dict[str, Any]:
    """Parse system_info from a JSON API response."""
    json_si = JSONSystemInfoParser(source)
    result = json_si.parse(resources)
    return result if isinstance(result, dict) else {}


def _parse_xml_sysinfo(
    source: XMLSystemInfoSource,
    resources: dict[str, Any],
) -> dict[str, Any]:
    """Parse system_info from XML element fields."""
    xml_si = XMLSystemInfoParser(source)
    result = xml_si.parse(resources)
    return result if isinstance(result, dict) else {}


# Wrappers keyed by format_tag. Combined with SYSTEM_INFO_SOURCE_MODELS
# below to build SYSINFO_PARSERS.
_SYSINFO_WRAPPERS_BY_TAG: dict[str, Callable[..., dict[str, Any]]] = {
    "html_fields": _parse_html_fields_sysinfo,
    "hnap": _parse_hnap_sysinfo,
    "javascript": _parse_js_sysinfo,
    "javascript_vars": _parse_js_vars_sysinfo,
    "json": _parse_json_sysinfo,
    "xml": _parse_xml_sysinfo,
}

# Maps source config type -> parser callable(source, resources) -> dict.
SYSINFO_PARSERS: dict[type, Callable[..., dict[str, Any]]] = {
    model: _SYSINFO_WRAPPERS_BY_TAG[model.format_tag] for model in SYSTEM_INFO_SOURCE_MODELS
}


# ---------------------------------------------------------------------------
# Merge utility (used by table and transposed factory functions)
# ---------------------------------------------------------------------------


def _merge_channels(
    primary: list[dict[str, Any]],
    merge_table: list[dict[str, Any]],
    merge_by: list[str],
) -> None:
    """Merge fields from a companion table into primary channels.

    Builds a lookup by the declared key fields, then enriches primary
    channels. Primary always wins on field conflicts.

    Per PARSING_SPEC.md Companion Tables (merge_by) section.
    """
    merge_map: dict[tuple[Any, ...], dict[str, Any]] = {}
    for ch in merge_table:
        key = tuple(ch.get(field) for field in merge_by)
        merge_map[key] = ch

    for ch in primary:
        key = tuple(ch.get(field) for field in merge_by)
        extra = merge_map.get(key, {})
        for field, value in extra.items():
            if field not in ch:
                ch[field] = value
