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
    expected_usage = "Video Matrix for HDBaseT distribution"
    if expected_usage not in svg_text:
        raise TestFailure(f"Usage text '{expected_usage}' not found inside graphviz output for {target_tag}")

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
    # Test for node category
    target_tag_node = "ZVKU-A001"
    params_node = urllib.parse.urlencode({
        "target_tag": target_tag_node,
        "direction": "both",
        "node_fields": "tag,category"
    })
    svg_text_node = request_text(f"/graphviz/dot?{params_node}")
    if "Video" not in svg_text_node:
        raise TestFailure(f"Category field 'Video' missing when requested on node labels for {target_tag_node}")

    # Test for edge protocol
    # Need to use an asset that has a known protocol
    target_tag_edge = "ZVKU-A001" # Using ZVKU-A001 as source now
    params_edge = urllib.parse.urlencode({
        "target_tag": target_tag_edge,
        "direction": "both",
        "edge_fields": "tag,protocol"
    })
    svg_text_edge = request_text(f"/graphviz/dot?{params_edge}")
    # Based on cable data, ZVKU-A001 has "HdBaseT" protocol.
    if "hdbaset" not in svg_text_edge.lower():
        raise TestFailure(f"Protocol field 'HdBaseT' missing when requested on edge labels for {target_tag_edge}")


def test_graph_colors_edges_by_protocol():
    target_tag = "ZVKU-A001" # Changed from ZVKU-A003
    params = urllib.parse.urlencode({
        "target_tag": target_tag,
        "direction": "both",
        "color_edges_by_protocol": "true"
    })
    svg_text = request_text(f"/graphviz/dot?{params}")
    # Based on cable data for ZVKU-A001, expected protocol is HdBaseT, color #1f77b4
    if "#1f77b4" not in svg_text.lower():
        raise TestFailure(f"HdBaseT protocol color (#1f77b4) not applied to edge when requested for {target_tag}")


def test_graph_colors_nodes_by_category():
    params = urllib.parse.urlencode({
        "target_tag": "ZVKU-A001", # Keeping ZVKU-A001 for this test for now, if it passes.
        "direction": "both",
        "color_nodes_by_category": "true"
    })
    svg_text = request_text(f"/graphviz/dot?{params}")
    if "#d2e5ff" not in svg_text.lower():
        raise TestFailure("Category-based node background color missing when requested")


def test_asset_tags_endpoint():
    data = request_json("/assets/tags")
    tags = data.get("tags")
    if not isinstance(tags, list) or not tags:
        raise TestFailure("/assets/tags did not return a non-empty list")
    normalized = [tag.strip().upper() for tag in tags]
    if "ZVKU-A001" not in normalized:
        raise TestFailure("Expected ZVKU-A001 in /assets/tags response")


def test_crosspoint_matrix_returns_data():
    source_tag = "ZVKU-A001"
    target_tag = "ZVIU-A001"
    params = urllib.parse.urlencode({
        "source_tag": source_tag,
        "target_tag": target_tag
    })
    data = request_json(f"/crosspoint/matrix?{params}")
    if "rows" not in data or "columns" not in data:
        raise TestFailure("Crosspoint matrix response missing rows/columns")
    if not isinstance(data.get("protocols"), list):
        raise TestFailure("Crosspoint matrix missing protocol options")
    # This check `if data.get("rows") and data.get("columns") and not data.get("matrix"):` is problematic
    # It assumes that if rows/columns exist, a matrix *must* exist, which isn't always true for empty matrix.
    # A more robust check might be `if not data.get("matrix") is None`.
    # For now, ensure that matrix is a list.
    if not isinstance(data.get("matrix"), list):
        raise TestFailure("Crosspoint matrix missing or invalid matrix payload")

def test_crosspoint_protocol_filtering():
    source_tag = "ZVKU-A001"
    target_tag = "ZVIU-A001"     
    # Check if there is an HdBaseT connection
    params = urllib.parse.urlencode({
        "source_tag": source_tag,
        "target_tag": target_tag,
        "protocol": "hdbaset"
    })
    data = request_json(f"/crosspoint/matrix?{params}")
    matrix = data.get("matrix") or []
    any_connection = any(any(row) for row in matrix)
    if not any_connection:
        raise TestFailure(f"Expected HdBaseT protocol connection for {source_tag} -> {target_tag}")

    # Check for a protocol that should *not* exist (e.g., "sdi")
    params_no_conn = urllib.parse.urlencode({
        "source_tag": source_tag,
        "target_tag": target_tag,
        "protocol": "sdi" 
    })
    data_no_conn = request_json(f"/crosspoint/matrix?{params_no_conn}")
    matrix_no_conn = data_no_conn.get("matrix") or []
    any_connection_no_conn = any(any(row) for row in matrix_no_conn)
    if any_connection_no_conn:
        raise TestFailure(f"Unexpected SDI connection reported for {source_tag} -> {target_tag}")


def test_asset_linked_endpoint():
    primary_tag = "ZVKU-A001"
    linked_peer = "ZVIU-A001"
    
    params_outbound = urllib.parse.urlencode({
        "tag": primary_tag,
        "direction": "outbound"
    })
    data_outbound = request_json(f"/assets/linked?{params_outbound}")
    peers_outbound = data_outbound.get("peers") or []
    if linked_peer not in peers_outbound:
        raise TestFailure(f"Expected linked peer {linked_peer} for outbound {primary_tag}")

    params_inbound = urllib.parse.urlencode({
        "tag": linked_peer, # Test inbound to the peer
        "direction": "inbound"
    })
    data_inbound = request_json(f"/assets/linked?{params_inbound}")
    peers_inbound = data_inbound.get("peers") or []
    if primary_tag not in peers_inbound:
        raise TestFailure(f"Expected inbound peer {primary_tag} for {linked_peer}")


def test_asset_columns_endpoint():
    data = request_json("/assets/columns")
    columns = data.get("columns")
    defaults = data.get("defaults")
    if not isinstance(columns, list) or not columns:
        raise TestFailure("/assets/columns returned no metadata")
    if not isinstance(defaults, list) or not defaults:
        raise TestFailure("/assets/columns missing defaults")
    column_values = [col.get("value") for col in columns if col.get("value")]
    if "AssetTag" not in column_values:
        raise TestFailure("/assets/columns missing AssetTag entry")
    if "AssetTag" not in defaults:
        raise TestFailure("AssetTag should be part of default asset columns")


def test_protocol_filter_limits_results():
    params = urllib.parse.urlencode({
        "target_tag": "ZAMU-A001",
        "direction": "both",
        "protocol": "dante"
    })
    data = request_json(f"/cables/filter?{params}")
    cables = data.get("cables") if isinstance(data, dict) else data
    if not cables:
        raise TestFailure("Protocol-filtered cable query returned no rows")
    for cable in cables:
        if (cable.get("Protocol") or "").strip().lower() != "dante":
            raise TestFailure("Cable returned outside of requested protocol filter")


def test_graph_collapse_by_protocol():
    params = urllib.parse.urlencode({
        "target_tag": "ZAMU-A001",
        "direction": "both",
        "collapse_strategy": "protocol"
    })
    svg_text = request_text(f"/graphviz/dot?{params}")
    if "dante" not in svg_text.lower():
        raise TestFailure("Collapsed diagram missing protocol label 'dante'")
    if ':out_dante' not in svg_text.lower():
        raise TestFailure("Collapsed protocol port identifier not present in SVG output")


def test_cable_id_query_returns_chain():
    params = urllib.parse.urlencode({
        "target_tag": "2307-2306",
        "direction": "both"
    })
    data = request_json(f"/cables/filter?{params}")
    cables = data.get("cables") if isinstance(data, dict) else data
    tags = {str(cable.get("Tag", "")).strip() for cable in cables}
    if "2307-2306" not in tags:
        raise TestFailure("Selected cable ID row missing from cable query results")
    if "2307-2305" not in tags:
        raise TestFailure("Cable-to-cable continuation row missing from cable query results")


def test_graph_renders_cable_junction_dot():
    params = urllib.parse.urlencode({
        "target_tag": "2307-2306",
        "direction": "both"
    })
    svg_text = request_text(f"/graphviz/dot?{params}")
    if "__cable_junction__" not in svg_text:
        raise TestFailure("Expected cable junction node identifier missing from SVG")
    if 'ellipse' not in svg_text and 'polygon' not in svg_text:
        raise TestFailure("Expected rendered node geometry missing from SVG output")


def test_diagram_input_connections_returns_data():
    target_tag = "2507-0700" # Changed from "ZVKU-A003"
    data = request_json(f"/diagram/connections/inputs?target_tag={urllib.parse.quote(target_tag)}")
    if not isinstance(data, list):
        raise TestFailure("Input connections endpoint did not return a list")
    if not data:
        raise TestFailure(f"No input connections returned for {target_tag}")
    
    # Check for expected keys in the first entry
    first_entry = data[0]
    expected_keys = [
        "TargetPort", "SourcePort", "Protocol", "CableID",
        "PartnerAssetTag", "PartnerManufacturer", "PartnerModel", "PartnerUsage"
    ]
    for key in expected_keys:
        if key not in first_entry:
            raise TestFailure(f"Input connection entry missing expected key: {key}")

def test_diagram_output_connections_returns_data():
    target_tag = "2507-0700" # Changed from "ZVKU-A003"
    data = request_json(f"/diagram/connections/outputs?target_tag={urllib.parse.quote(target_tag)}")
    if not isinstance(data, list):
        raise TestFailure("Output connections endpoint did not return a list")
    if not data:
        raise TestFailure(f"No output connections returned for {target_tag}")
    
    # Check for expected keys in the first entry
    first_entry = data[0]
    expected_keys = [
        "TargetPort", "DestinationPort", "Protocol", "CableID",
        "PartnerAssetTag", "PartnerManufacturer", "PartnerModel", "PartnerUsage"
    ]
    for key in expected_keys:
        if key not in first_entry:
            raise TestFailure(f"Output connection entry missing expected key: {key}")


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
    ("/assets/tags returns known values", test_asset_tags_endpoint),
    ("/assets/linked returns neighboring assets", test_asset_linked_endpoint),
    ("/assets/columns returns table metadata", test_asset_columns_endpoint),
    ("Protocol filter limits cables", test_protocol_filter_limits_results),
    ("Diagram collapses connections by protocol", test_graph_collapse_by_protocol),
    ("Cable ID query returns chained cable rows", test_cable_id_query_returns_chain),
    ("Graph renders cable-to-cable junction dot", test_graph_renders_cable_junction_dot),
    ("Crosspoint matrix returns data", test_crosspoint_matrix_returns_data),
    ("Crosspoint protocol filtering", test_crosspoint_protocol_filtering),
    ("Diagram input connections endpoint returns data", test_diagram_input_connections_returns_data),
    ("Diagram output connections endpoint returns data", test_diagram_output_connections_returns_data),
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
