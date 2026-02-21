#!/usr/bin/env python3
"""
Manual backend test suite for the UAC Tech webapp.

Run with: python3 tests/run_tests.py
Optionally set WEBAPP_API_BASE to override the backend URL (default http://localhost:9000).
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, List, Tuple


API_BASE = os.environ.get("WEBAPP_API_BASE", "http://localhost:9000").rstrip("/")
DEFAULT_TIMEOUT = float(os.environ.get("WEBAPP_TEST_TIMEOUT", "10"))


class TestFailure(Exception):
    """Raised when an individual test fails."""


def request_json(path: str):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TestFailure(f"HTTP {exc.code} for {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise TestFailure(f"Request failed for {url}: {exc}") from exc


def request_text(path: str):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"Accept": "text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TestFailure(f"HTTP {exc.code} for {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise TestFailure(f"Request failed for {url}: {exc}") from exc


def test_backend_root():
    data = request_json("/")
    if "message" not in data:
        raise TestFailure("Root endpoint missing 'message'")


def test_asset_search_returns_usage():
    target_tag = "ZVKU-A001"
    data = request_json(f"/assets/search?asset_tag={urllib.parse.quote(target_tag)}")
    if not data:
        raise TestFailure(f"No asset rows returned for {target_tag}")
    row = data[0]
    if row.get("AssetTag", "").strip().upper() != target_tag:
        raise TestFailure(f"Unexpected asset tag in response: {row.get('AssetTag')}")
    if not row.get("Usage"):
        raise TestFailure("Asset row missing Usage value")


def test_cable_filter_has_rows():
    target_tag = "2507-0700"
    data = request_json(f"/cables/filter?target_tag={urllib.parse.quote(target_tag)}&direction=both")
    cables = data.get("cables") if isinstance(data, dict) else data
    if not cables:
        raise TestFailure(f"No cables returned for {target_tag}")
    sample = cables[0]
    if "SrcTag" not in sample or "DstTag" not in sample:
        raise TestFailure("Cable row missing SrcTag/DstTag fields")


def test_graph_contains_usage_line():
    target_tag = "ZVKU-A001"
    svg_text = request_text(f"/graphviz/dot?target_tag={urllib.parse.quote(target_tag)}&direction=both")
    expected_usage = "Legacy switcher for HDBaseT distribution"
    if expected_usage not in svg_text:
        raise TestFailure("Usage text not found inside graphviz output")


def test_graph_respects_custom_fields():
    target_tag = "ZVKU-A001"
    params = urllib.parse.urlencode({
        "target_tag": target_tag,
        "direction": "both",
        "node_fields": "tag",
        "edge_fields": "tag"
    })
    svg_text = request_text(f"/graphviz/dot?{params}")
    if "Legacy switcher for HDBaseT distribution" in svg_text:
        raise TestFailure("Usage line rendered despite node_fields=tag")
    if "Manufacturer" in svg_text:
        raise TestFailure("Manufacturer text rendered despite node_fields=tag")


def test_diagram_options_lists_all_fields():
    data = request_json("/diagram/options")
    node_payload = data.get("node") or {}
    edge_payload = data.get("edge") or {}
    node_defaults = node_payload.get("defaults") or []
    node_options = node_payload.get("options") or []
    edge_defaults = edge_payload.get("defaults") or []
    edge_options = edge_payload.get("options") or []
    if not node_defaults or not edge_defaults:
        raise TestFailure("Diagram options endpoint missing defaults")
    node_values = [opt.get("value") for opt in node_options if opt.get("value")]
    edge_values = [opt.get("value") for opt in edge_options if opt.get("value")]
    if node_values[:len(node_defaults)] != node_defaults:
        raise TestFailure("Node defaults are not listed first")
    if edge_values[:len(edge_defaults)] != edge_defaults:
        raise TestFailure("Edge defaults are not listed first")
    if len(set(node_values)) <= len(node_defaults):
        raise TestFailure("Node options missing non-default fields")
    if len(set(edge_values)) <= len(edge_defaults):
        raise TestFailure("Edge options missing non-default fields")


def test_graph_renders_additional_fields():
    params = urllib.parse.urlencode({
        "target_tag": "ZVKU-A001",
        "direction": "both",
        "node_fields": "tag,category"
    })
    svg_text = request_text(f"/graphviz/dot?{params}")
    if "Video" not in svg_text:
        raise TestFailure("Category field missing when requested on node labels")
    params = urllib.parse.urlencode({
        "target_tag": "ZVKU-A003",
        "direction": "both",
        "edge_fields": "tag,protocol"
    })
    svg_text = request_text(f"/graphviz/dot?{params}")
    if "sdi" not in svg_text.lower():
        raise TestFailure("Protocol field missing when requested on edge labels")


def test_graph_colors_edges_by_protocol():
    params = urllib.parse.urlencode({
        "target_tag": "ZVKU-A003",
        "direction": "both",
        "color_edges_by_protocol": "true"
    })
    svg_text = request_text(f"/graphviz/dot?{params}")
    if "#00b050" not in svg_text.lower():
        raise TestFailure("SDI protocol color not applied to edge when requested")


def test_graph_colors_nodes_by_category():
    params = urllib.parse.urlencode({
        "target_tag": "ZVKU-A001",
        "direction": "both",
        "color_nodes_by_category": "true"
    })
    svg_text = request_text(f"/graphviz/dot?{params}")
    if "#d2e5ff" not in svg_text.lower():
        raise TestFailure("Category-based node background color missing when requested")


TESTS: List[Tuple[str, Callable[[], None]]] = [
    ("GET /", test_backend_root),
    ("Asset search returns usage", test_asset_search_returns_usage),
    ("Cable filter returns rows", test_cable_filter_has_rows),
    ("Graph contains usage line", test_graph_contains_usage_line),
    ("Graph respects custom field selections", test_graph_respects_custom_fields),
    ("Diagram options list defaults and additional fields", test_diagram_options_lists_all_fields),
    ("Graph renders newly requested fields", test_graph_renders_additional_fields),
    ("Graph colors edges by protocol", test_graph_colors_edges_by_protocol),
    ("Graph colors nodes by category", test_graph_colors_nodes_by_category),
]


def main():
    print(f"Running {len(TESTS)} tests against {API_BASE}")
    passed = 0
    for name, func in TESTS:
        try:
            func()
        except TestFailure as exc:
            print(f"[FAIL] {name}: {exc}")
        except Exception as exc:
            print(f"[ERROR] {name}: {exc}", file=sys.stderr)
        else:
            print(f"[PASS] {name}")
            passed += 1
    total = len(TESTS)
    print(f"Completed {total} tests: {passed} passed, {total - passed} failed")
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
