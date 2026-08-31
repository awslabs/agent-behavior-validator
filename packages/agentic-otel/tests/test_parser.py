# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for shared OTEL parsing utilities."""

from agentic_otel.parser import (
    extract_spans, find_root, parse_attrs, parse_timestamp,
    safe_json_parse, sort_spans_by_time, get_span_start_ns, spans_overlap,
)
from datetime import datetime, timezone


# --- extract_spans ---

def test_extract_camelcase():
    trace = {"resourceSpans": [{"scopeSpans": [{"spans": [{"name": "a"}]}]}]}
    assert len(extract_spans(trace)) == 1

def test_extract_snakecase():
    trace = {"resource_spans": [{"scope_spans": [{"spans": [{"name": "b"}]}]}]}
    assert len(extract_spans(trace)) == 1

def test_extract_flat():
    trace = {"spans": [{"name": "c"}]}
    assert len(extract_spans(trace)) == 1

def test_extract_empty():
    assert extract_spans({}) == []
    assert extract_spans({"resourceSpans": []}) == []


# --- find_root ---

def test_find_root_by_empty_parent():
    spans = [
        {"spanId": "child", "parentSpanId": "root"},
        {"spanId": "root", "parentSpanId": ""},
    ]
    assert find_root(spans)["spanId"] == "root"

def test_find_root_fallback_earliest():
    spans = [
        {"spanId": "b", "parentSpanId": "x", "startTimeUnixNano": "200"},
        {"spanId": "a", "parentSpanId": "y", "startTimeUnixNano": "100"},
    ]
    assert find_root(spans)["spanId"] == "a"

def test_find_root_empty():
    assert find_root([]) == {}


# --- parse_attrs ---

def test_parse_attrs_list():
    attrs = [
        {"key": "k1", "value": {"stringValue": "v1"}},
        {"key": "k2", "value": {"intValue": 42}},
        {"key": "k3", "value": {"boolValue": True}},
    ]
    result = parse_attrs(attrs)
    assert result["k1"] == "v1"
    assert result["k2"] == 42
    assert result["k3"] is True

def test_parse_attrs_dict():
    result = parse_attrs({"key": "value"})
    assert result["key"] == "value"

def test_parse_attrs_empty():
    assert parse_attrs([]) == {}
    assert parse_attrs({}) == {}


# --- parse_timestamp ---

def test_parse_timestamp_valid():
    dt = parse_timestamp("1711000000000000000")
    assert dt.year == 2024

def test_parse_timestamp_none():
    dt = parse_timestamp(None)
    assert isinstance(dt, datetime)

def test_parse_timestamp_zero():
    dt = parse_timestamp(0)
    assert isinstance(dt, datetime)


# --- safe_json_parse ---

def test_parse_json_string():
    assert safe_json_parse('{"a": 1}') == {"a": 1}

def test_parse_non_json():
    assert safe_json_parse("hello") == "hello"

def test_parse_none():
    assert safe_json_parse(None) is None

def test_parse_dict_passthrough():
    d = {"a": 1}
    assert safe_json_parse(d) is d


# --- sort and overlap ---

def test_sort_by_time():
    spans = [
        {"startTimeUnixNano": "300"},
        {"startTimeUnixNano": "100"},
        {"startTimeUnixNano": "200"},
    ]
    sorted_spans = sort_spans_by_time(spans)
    assert get_span_start_ns(sorted_spans[0]) == 100
    assert get_span_start_ns(sorted_spans[2]) == 300

def test_overlap_true():
    a = {"startTimeUnixNano": "100", "endTimeUnixNano": "300"}
    b = {"startTimeUnixNano": "200", "endTimeUnixNano": "400"}
    assert spans_overlap(a, b)

def test_overlap_false():
    a = {"startTimeUnixNano": "100", "endTimeUnixNano": "200"}
    b = {"startTimeUnixNano": "300", "endTimeUnixNano": "400"}
    assert not spans_overlap(a, b)

def test_overlap_missing_end():
    a = {"startTimeUnixNano": "100"}
    b = {"startTimeUnixNano": "200", "endTimeUnixNano": "300"}
    assert not spans_overlap(a, b)

def test_overlap_both_missing_end():
    a = {"startTimeUnixNano": "100"}
    b = {"startTimeUnixNano": "200"}
    assert not spans_overlap(a, b)


# --- timestamp edge cases ---

def test_timestamp_valid():
    from agentic_otel.parser import parse_timestamp
    dt = parse_timestamp(1700000000000000000)  # ~2023-11-14
    assert dt.year == 2023

def test_timestamp_string():
    from agentic_otel.parser import parse_timestamp
    dt = parse_timestamp("1700000000000000000")
    assert dt.year == 2023

def test_timestamp_missing_returns_epoch():
    from agentic_otel.parser import parse_timestamp, _EPOCH
    assert parse_timestamp(None) == _EPOCH
    assert parse_timestamp(0) == _EPOCH
    assert parse_timestamp("") == _EPOCH

def test_timestamp_invalid_returns_epoch():
    from agentic_otel.parser import parse_timestamp, _EPOCH
    assert parse_timestamp("not-a-number") == _EPOCH

def test_timestamp_negative_returns_epoch():
    from agentic_otel.parser import parse_timestamp, _EPOCH
    # Negative timestamp (before epoch) causes OSError on some platforms
    result = parse_timestamp(-99999999999999999999)
    assert result == _EPOCH


# --- attribute edge cases ---

def test_attrs_missing_key():
    from agentic_otel.parser import parse_attrs
    result = parse_attrs([{"value": {"stringValue": "v"}}])
    assert result.get("") == "v"

def test_attrs_missing_value():
    from agentic_otel.parser import parse_attrs
    result = parse_attrs([{"key": "k"}])
    assert result["k"] == {}

def test_attrs_empty_list():
    from agentic_otel.parser import parse_attrs
    assert parse_attrs([]) == {}
