import hashlib
import pandas as pd
import numpy as np
import html # Import html module
import graphviz # Import graphviz
import re
from fastapi import FastAPI, HTTPException, Query # Import Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response # Import Response for SVG output
from pydantic import BaseModel
from typing import Optional, List, Set, Dict, Tuple

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def clean_dataframe_for_json(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans a DataFrame by converting all values to strings or empty strings for JSON serialization.
    Handles NaN, NaT, Inf by converting to empty string "". Datetimes are converted to ISO format.
    """
    df_cleaned = df.copy()
    
    for col in df_cleaned.columns:
        # Replace all problematic float values (NaN, Inf, -Inf) and pd.NA with empty string ""
        df_cleaned[col] = df_cleaned[col].replace({np.nan: "", np.inf: "", -np.inf: "", pd.NA: ""})

        # Handle explicit datetime objects (pd.NaT should already be converted to "" by replace)
        if pd.api.types.is_datetime64_any_dtype(df_cleaned[col]):
            df_cleaned[col] = df_cleaned[col].apply(lambda x: x.isoformat() if x != "" else "") # Use "" not None here
        else:
            # For all other columns, convert to string (or empty string if empty)
            df_cleaned[col] = df_cleaned[col].apply(lambda x: str(x) if x != "" else "") # Use "" not None here
            
    return df_cleaned

# --- Data Loading ---
def normalize_tag_value(value: Optional[str]) -> str:
    """Returns a canonical representation for asset/cable tags."""
    if value is None:
        return ""
    return str(value).strip().upper()


def load_assets_data():
    """Loads asset data from uac_assets.xlsx."""
    try:
        df_assets = pd.read_excel("../data/uac_assets.xlsx", sheet_name="assets")
        # Filter out rows where AssetTag is NaN, as these seem to be summary/non-asset rows
        df_assets = df_assets.dropna(subset=["AssetTag"])
        # Force all columns to object dtype to prevent NaN re-introduction issues
        df_assets = df_assets.astype(object)
        df_assets["AssetTag"] = df_assets["AssetTag"].astype(str).str.strip()
        df_assets["AssetTagNorm"] = df_assets["AssetTag"].str.upper()
        return df_assets
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading asset data: {e}")

def load_cables_data():
    """Loads cable data from uac_cables.xlsx."""
    try:
        df_cables = pd.read_excel("../data/uac_cables.xlsx", sheet_name="Cables")
        # Force all columns to object dtype to prevent NaN re-introduction issues
        df_cables = df_cables.astype(object)
        df_cables["SrcTag"] = df_cables["SrcTag"].astype(str).str.strip()
        df_cables["DstTag"] = df_cables["DstTag"].astype(str).str.strip()
        df_cables["SrcTagNorm"] = df_cables["SrcTag"].str.upper()
        df_cables["DstTagNorm"] = df_cables["DstTag"].str.upper()
        return df_cables
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading cable data: {e}")

# Load data globally for the application to avoid reloading on each request
df_assets = load_assets_data()
df_cables = load_cables_data()
ASSET_TAG_LOOKUP: Dict[str, str] = {}
VALID_ASSET_TAGS_NORMALIZED: Set[str] = set()
CABLE_TAG_LOOKUP: Dict[str, str] = {}
ALL_KNOWN_TAGS_NORMALIZED: Set[str] = set()

ASSET_FIELD_MAP: Dict[str, str] = {}  # canonical -> column name
ASSET_FIELD_LABELS: Dict[str, str] = {}
CABLE_FIELD_MAP: Dict[str, str] = {}
CABLE_FIELD_LABELS: Dict[str, str] = {}
NODE_FIELD_OPTIONS: Set[str] = set()
EDGE_FIELD_OPTIONS: Set[str] = set()
DEFAULT_NODE_FIELDS = ["tag", "manufacturer", "model", "usage"]
DEFAULT_EDGE_FIELDS = ["tag", "type", "ports", "usage"]
DEFAULT_NODE_BACKGROUND = "#D9E8FB"
CROSSPOINT_HEADER_LABELS = {
    "port": "Port",
    "usage": "Usage",
    "protocol": "Protocol",
    "tag": "Cable Tag",
    "type": "Cable Type",
    "notes": "Notes",
}
CROSSPOINT_HEADER_FIELDS = set(CROSSPOINT_HEADER_LABELS.keys())
CROSSPOINT_DEFAULT_FIELDS = ["port", "usage"]
PROTOCOL_COLOR_MAP = {
    "sdi": "#00B050",
    "hdmi": "#ED7D31",
    "ethernet": "#0070C0",
    "hdbaset": "#1F77B4",
    "dante": "#C00000",
    "dmx": "#7030A0",
    "rf": "#996633",
    "gigaace": "#2E75B6",
    "dx-link": "#4BACC6",
    "aa-line": "#70AD47",
    "aa-mic": "#548235",
    "aa-amp": "#92D050",
    "comp-video": "#FFC000",
    "vga": "#FABF8F",
    "viscaip": "#B8359F",
    "unused": "#A6A6A6",
}
CATEGORY_COLOR_MAP = {
    "video": "#BBD7FF",
    "audio": "#F8C471",
    "lighting": "#F7B7D2",
    "network": "#C6E0B4",
    "power": "#FAD7AC",
    "security": "#D5A6BD",
    "hardware": "#E2EFDA",
    "misc": "#E4DFEC",
    "music": "#FFE699",
    "usb": "#FFD966",
}
DEFAULT_PROTOCOL_COLOR = "#6C757D"
DEFAULT_CATEGORY_COLOR = "#DDEBF7"
COLLAPSE_OPTIONS = {"none", "protocol", "type"}
ASSET_TABLE_DEFAULT_COLUMNS = ["AssetTag", "Model", "Manufacturer", "Desc", "Usage"]
ASSET_TABLE_LABEL_OVERRIDES = {
    "AssetTag": "Asset Tag",
    "Desc": "Description",
    "SN": "Serial Number",
}

def rebuild_lookup_sets() -> None:
    """Rebuilds lookup dictionaries for asset and cable tags."""
    global ASSET_TAG_LOOKUP, VALID_ASSET_TAGS_NORMALIZED, CABLE_TAG_LOOKUP, ALL_KNOWN_TAGS_NORMALIZED
    ASSET_TAG_LOOKUP = dict(zip(df_assets["AssetTagNorm"], df_assets["AssetTag"]))
    VALID_ASSET_TAGS_NORMALIZED = set(ASSET_TAG_LOOKUP.keys())

    CABLE_TAG_LOOKUP = {}
    for tag in pd.concat([df_cables["SrcTag"], df_cables["DstTag"]]).dropna():
        norm = normalize_tag_value(tag)
        if norm and norm not in CABLE_TAG_LOOKUP:
            CABLE_TAG_LOOKUP[norm] = str(tag).strip()

    ALL_KNOWN_TAGS_NORMALIZED = VALID_ASSET_TAGS_NORMALIZED.union(CABLE_TAG_LOOKUP.keys())


class CableFilterResponse(BaseModel):
    cables: List[Dict[str, str]]
    asset_tags: List[str]
    primary_target: str


def normalize_tag_list(tags_value: Optional[str]) -> List[str]:
    """Splits a comma-separated tag string and normalizes each entry."""
    if not tags_value:
        return []
    if not isinstance(tags_value, str):
        tags_value = str(tags_value)
    normalized = []
    for raw_tag in tags_value.split(','):
        norm = normalize_tag_value(raw_tag)
        if norm:
            normalized.append(norm)
    return normalized


def denormalize_tags(normalized_tags: Set[str]) -> Set[str]:
    """Converts normalized tags back to their display form if possible."""
    display_values: Set[str] = set()
    for tag in normalized_tags:
        if not tag:
            continue
        display_values.add(ASSET_TAG_LOOKUP.get(tag) or CABLE_TAG_LOOKUP.get(tag) or tag)
    return display_values


def canonical_display_tag(tag_value: Optional[str]) -> str:
    """Returns a consistent, display-friendly representation of a tag value."""
    norm = normalize_tag_value(tag_value)
    if not norm:
        return ""
    return ASSET_TAG_LOOKUP.get(norm) or CABLE_TAG_LOOKUP.get(norm) or norm


def reload_dataframes() -> None:
    """Reloads the global asset and cable DataFrames and associated lookup sets."""
    global df_assets, df_cables, ASSET_TAG_LOOKUP, VALID_ASSET_TAGS_NORMALIZED
    df_assets = load_assets_data()
    df_cables = load_cables_data()
    rebuild_lookup_sets()
    rebuild_field_option_maps()


def canonicalize_field_key(label: str) -> str:
    if not label:
        return ""
    sanitized = re.sub(r"[^0-9a-zA-Z]+", "_", str(label)).strip("_")
    return sanitized.lower()


def prettify_field_label(label: str) -> str:
    if not label:
        return ""
    original = str(label).strip()
    spaced = re.sub(r"(_)|(?<=[a-z0-9])(?=[A-Z])", " ", original)
    cleaned = re.sub(r"\s+", " ", spaced).strip()
    return cleaned


def rebuild_field_option_maps() -> None:
    """Builds lookup maps for node/edge field selections."""
    global ASSET_FIELD_MAP, ASSET_FIELD_LABELS, CABLE_FIELD_MAP, CABLE_FIELD_LABELS
    global NODE_FIELD_OPTIONS, EDGE_FIELD_OPTIONS

    ASSET_FIELD_MAP = {}
    ASSET_FIELD_LABELS = {"tag": "Tag"}
    excluded_asset_columns = {"AssetTagNorm"}
    for column in df_assets.columns:
        if column in excluded_asset_columns:
            continue
        canonical = canonicalize_field_key(column)
        if not canonical or canonical == "tag":
            continue
        ASSET_FIELD_MAP[canonical] = column
        ASSET_FIELD_LABELS[canonical] = prettify_field_label(column)

    CABLE_FIELD_MAP = {}
    CABLE_FIELD_LABELS = {
        "tag": "Tag",
        "ports": "In-Port → Out-Port",
    }
    excluded_cable_columns = {"SrcTagNorm", "DstTagNorm"}
    for column in df_cables.columns:
        if column in excluded_cable_columns:
            continue
        canonical = canonicalize_field_key(column)
        if not canonical or canonical in {"tag", "ports"}:
            continue
        CABLE_FIELD_MAP[canonical] = column
        CABLE_FIELD_LABELS[canonical] = prettify_field_label(column)

    NODE_FIELD_OPTIONS = set(ASSET_FIELD_LABELS.keys())
    EDGE_FIELD_OPTIONS = set(CABLE_FIELD_LABELS.keys())


rebuild_lookup_sets()
rebuild_field_option_maps()


@app.get("/assets/columns")
async def get_asset_columns():
    """Returns metadata for asset table column selection."""
    options = []
    for column in df_assets.columns:
        label = ASSET_TABLE_LABEL_OVERRIDES.get(column, prettify_field_label(column))
        options.append({
            "value": column,
            "label": label,
        })
    defaults: List[str] = []
    for default in ASSET_TABLE_DEFAULT_COLUMNS:
        if default in df_assets.columns:
            defaults.append(default)
        elif default.lower() == "make" and "Model" in df_assets.columns:
            defaults.append("Model")
    if not defaults:
        defaults = ["AssetTag"]
    return {"columns": options, "defaults": defaults}


def clamp(value: float, min_value: float = 0.0, max_value: float = 255.0) -> int:
    return int(max(min_value, min(max_value, value)))


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    value = hex_color.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return (221, 235, 247)
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % tuple(clamp(channel) for channel in rgb)


def lighten_color(hex_color: str, factor: float = 0.65) -> str:
    r, g, b = hex_to_rgb(hex_color)
    r = r + (255 - r) * factor
    g = g + (255 - g) * factor
    b = b + (255 - b) * factor
    return rgb_to_hex((r, g, b))


def hash_color_from_text(value: str, pastel: bool = False) -> str:
    if not value:
        return DEFAULT_CATEGORY_COLOR if pastel else DEFAULT_PROTOCOL_COLOR
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()
    # Use first 6 hex chars
    base_color = f"#{digest[:6]}"
    return lighten_color(base_color, 0.7) if pastel else base_color


def get_protocol_color(protocol_value: Optional[str]) -> str:
    if not protocol_value:
        return DEFAULT_PROTOCOL_COLOR
    key = str(protocol_value).strip().lower()
    if not key:
        return DEFAULT_PROTOCOL_COLOR
    return PROTOCOL_COLOR_MAP.get(key) or hash_color_from_text(key, pastel=False)


def get_category_color(category_value: Optional[str]) -> str:
    if not category_value:
        return DEFAULT_CATEGORY_COLOR
    key = str(category_value).strip().lower()
    if not key:
        return DEFAULT_CATEGORY_COLOR
    return lighten_color(CATEGORY_COLOR_MAP.get(key) or hash_color_from_text(key, pastel=True), 0.35)


def format_display_value(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    return text


def normalize_port_value(value: object) -> str:
    text = format_display_value(value)
    return text


def collect_unique_texts(series: pd.Series) -> List[str]:
    uniques: List[str] = []
    seen = set()
    for raw in series.dropna():
        text = format_display_value(raw)
        if text and text not in seen:
            seen.add(text)
            uniques.append(text)
    return uniques


def build_crosspoint_label(port_value: str, subset: pd.DataFrame, fields: List[str]) -> str:
    label_parts: List[str] = []
    for field_key in fields:
        text = ""
        if field_key == "port":
            text = format_display_value(port_value) or "(No Port)"
        elif field_key == "usage":
            text = ", ".join(collect_unique_texts(subset["Usage"]))
        elif field_key == "protocol":
            text = ", ".join(collect_unique_texts(subset["Protocol"]))
        elif field_key == "tag":
            text = ", ".join(collect_unique_texts(subset["Tag"]))
        elif field_key == "type":
            text = ", ".join(collect_unique_texts(subset["Type"]))
        elif field_key == "notes" and "Notes" in subset.columns:
            text = ", ".join(collect_unique_texts(subset["Notes"]))
        text = text.strip()
        if text:
            label_parts.append(text)
    if not label_parts:
        if format_display_value(port_value):
            label_parts.append(format_display_value(port_value))
        else:
            label_parts.append("(No Port)")
    return " | ".join(label_parts)


def parse_expansion_param(
    expansions: Optional[str],
    default_direction: str,
    target_norm: str,
) -> Dict[str, Set[str]]:
    """
    Parses the expansions query parameter into a mapping of node -> direction set.
    Always ensures the target node has at least the default direction applied.
    """
    direction_map: Dict[str, Set[str]] = {}

    def direction_to_set(direction_value: str) -> Set[str]:
        if direction_value == "in":
            return {"in"}
        if direction_value == "out":
            return {"out"}
        return {"in", "out"}

    direction_map[target_norm] = direction_to_set(default_direction)

    if not expansions:
        return direction_map

    parts = [chunk.strip() for chunk in expansions.split(";") if chunk.strip()]
    for part in parts:
        if ":" in part:
            tag_part, dir_part = part.split(":", 1)
        else:
            tag_part, dir_part = part, "both"

        norm_tag = normalize_tag_value(tag_part)
        if not norm_tag:
            continue
        direction_set = direction_to_set(dir_part.strip().lower())
        if norm_tag not in direction_map:
            direction_map[norm_tag] = set()
        direction_map[norm_tag].update(direction_set)

    return direction_map


def parse_field_selection(value: Optional[str], allowed: Set[str], default: List[str]) -> List[str]:
    if not value:
        return list(default)
    if not isinstance(value, str):
        value = str(value)
    selections = [item.strip().lower() for item in value.split(',') if item.strip()]
    cleaned = [item for item in selections if item in allowed]
    return cleaned or list(default)


def normalize_asset_field_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return text if text.lower() != "nan" else ""


def get_asset_field_value(asset_record: Dict[str, object], field_key: str, fallback_tag: str) -> str:
    if field_key == "tag":
        return fallback_tag
    column = ASSET_FIELD_MAP.get(field_key)
    if not column:
        return ""
    if not asset_record:
        return ""
    raw_value = asset_record.get(column, "")
    return normalize_asset_field_value(raw_value)


def get_edge_field_value(row: pd.Series, field_key: str) -> str:
    if field_key == "tag":
        raw = row.get("Tag", "")
        return html.escape(normalize_asset_field_value(raw)) if raw else ""
    if field_key == "ports":
        src_port = normalize_asset_field_value(row.get("SrcPort", ""))
        dst_port = normalize_asset_field_value(row.get("DstPort", ""))
        if src_port and dst_port:
            return f"{html.escape(src_port)} → {html.escape(dst_port)}"
        if src_port:
            return html.escape(src_port)
        if dst_port:
            return html.escape(dst_port)
        return ""
    column = CABLE_FIELD_MAP.get(field_key)
    if not column:
        return ""
    raw = row.get(column, "")
    value = normalize_asset_field_value(raw)
    return html.escape(value) if value else ""


def build_field_option_payload(labels: Dict[str, str], defaults: List[str]) -> Dict[str, object]:
    default_values = [field for field in defaults if field in labels]
    remaining = sorted(
        [field for field in labels.keys() if field not in default_values],
        key=lambda key: labels[key].lower(),
    )
    ordered = default_values + remaining
    return {
        "defaults": default_values,
        "options": [
            {
                "value": field,
                "label": labels[field],
                "selected": field in default_values,
            }
            for field in ordered
        ],
    }


def collapse_label_for_row(row: pd.Series, strategy: str) -> str:
    raw_value = ""
    if strategy == "protocol":
        raw_value = row.get("Protocol", "")
    elif strategy == "type":
        raw_value = row.get("Type", "")
    label = format_display_value(raw_value)
    return label or "Unknown"


def sanitize_port_identifier(label: str, direction: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "_", label.strip().lower())
    if not base:
        base = "unknown"
    return f"{direction}_{base}"


@app.get("/")
async def read_root():
    return {"message": "Welcome to the UAC Tech Documentation API"}


@app.post("/data/reload")
async def reload_data():
    """Forces the backend to reload the asset and cable spreadsheets."""
    try:
        reload_dataframes()
        return {
            "status": "ok",
            "assets": len(df_assets),
            "cables": len(df_cables),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to reload data: {exc}")


@app.get("/diagram/options")
async def get_diagram_field_options():
    """Exposes available node/edge fields for the frontend multi-select controls."""
    return {
        "node": build_field_option_payload(ASSET_FIELD_LABELS, DEFAULT_NODE_FIELDS),
        "edge": build_field_option_payload(CABLE_FIELD_LABELS, DEFAULT_EDGE_FIELDS),
        "crosspoint": build_field_option_payload(CROSSPOINT_HEADER_LABELS, CROSSPOINT_DEFAULT_FIELDS),
    }

# --- Graphviz DOT Generation Function ---
def generate_dot_string(
    filtered_cables: pd.DataFrame,
    assets_df: pd.DataFrame,
    all_nodes_to_render: Set[str],
    node_fields: List[str],
    edge_fields: List[str],
    color_nodes_by_category: bool,
    color_edges_by_protocol: bool,
    collapse_strategy: str,
) -> str:
    """
    Generates a Graphviz DOT string from filtered cable and asset data,
    with custom node shapes and port displays.
    Ensures all specified nodes in `all_nodes_to_render` are included, even if isolated.
    """
    dot_nodes = set(all_nodes_to_render) # Initialize with all nodes that need to be rendered
    node_ports = {node_tag: {'src': {}, 'dst': {}} for node_tag in all_nodes_to_render} # Pre-fill node_ports
    
    # Collect all ports for nodes that have connecting cables
    collapse_mode = collapse_strategy in {"protocol", "type"}

    if collapse_mode:
        grouped_entries: Dict[Tuple[str, str, str], List[pd.Series]] = {}
        for _, row in filtered_cables.iterrows():
            src_tag = str(row["SrcTag"])
            dst_tag = str(row["DstTag"])
            group_label = collapse_label_for_row(row, collapse_strategy)
            key = (src_tag, dst_tag, group_label)
            grouped_entries.setdefault(key, []).append(row)
            dot_nodes.add(src_tag)
            dot_nodes.add(dst_tag)
        # Build node port labels per grouping value/direction
        for (src_tag, dst_tag, group_label), rows in grouped_entries.items():
            src_port_id = sanitize_port_identifier(group_label, "out")
            dst_port_id = sanitize_port_identifier(group_label, "in")
            if src_tag not in node_ports:
                node_ports[src_tag] = {'src': {}, 'dst': {}}
            if dst_tag not in node_ports:
                node_ports[dst_tag] = {'src': {}, 'dst': {}}
            node_ports[src_tag]['src'][src_port_id] = group_label
            node_ports[dst_tag]['dst'][dst_port_id] = group_label
    else:
        for _, row in filtered_cables.iterrows():
            src_tag = str(row["SrcTag"]) # Ensure string
            dst_tag = str(row["DstTag"]) # Ensure string
            src_port = str(row["SrcPort"]) # Ensure string
            dst_port = str(row["DstPort"]) # Ensure string

            # Ensure these nodes exist in dot_nodes (they should if logic is correct, but safe check)
            dot_nodes.add(src_tag)
            dot_nodes.add(dst_tag)

            # Ensure node_ports entries exist for src/dst tags
            if src_tag not in node_ports:
                node_ports[src_tag] = {'src': {}, 'dst': {}}
            if dst_tag not in node_ports:
                node_ports[dst_tag] = {'src': {}, 'dst': {}}

            if src_port != "":
                node_ports[src_tag]['src'][src_port] = src_port

            if dst_port != "":
                node_ports[dst_tag]['dst'][dst_port] = dst_port

    node_definitions = []
    # Define nodes with HTML-like labels for ports and asset info
    for node_tag_val in sorted([str(n) for n in list(dot_nodes)]): # Iterate over all collected nodes
        asset_info = assets_df[assets_df["AssetTag"] == node_tag_val]
        asset_record = asset_info.iloc[0].to_dict() if not asset_info.empty else {}
        display_tag = str(node_tag_val).strip()
        category_value = asset_record.get("Category") if asset_record else ""
        node_bg_color = DEFAULT_NODE_BACKGROUND
        if color_nodes_by_category and category_value:
            node_bg_color = get_category_color(category_value)

        center_rows = []
        for field_key in node_fields:
            field_value = get_asset_field_value(asset_record, field_key, display_tag)
            if field_key == "tag":
                center_rows.append(f'<TR><TD ALIGN="CENTER"><B>{html.escape(field_value)}</B></TD></TR>')
                continue
            if not field_value:
                continue
            center_rows.append(f'<TR><TD ALIGN="CENTER">{html.escape(field_value)}</TD></TR>')
        if not center_rows:
            center_rows.append(f'<TR><TD ALIGN="CENTER"><B>{html.escape(display_tag)}</B></TD></TR>')
        center_content = '<TABLE BORDER="0" CELLBORDER="0" CELLPADDING="1">' + "".join(center_rows) + '</TABLE>'

        # Build DstPorts column
        dst_ports_content = ""
        dst_port_items = node_ports.get(node_tag_val, {}).get('dst', {})
        sorted_dst_ports = sorted(dst_port_items.items(), key=lambda item: item[1].lower())
        if sorted_dst_ports:
            dst_ports_content = '<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="1">' # Changed CELLBORDER to 1
            for port_id, label in sorted_dst_ports:
                dst_ports_content += f'<TR><TD PORT="{html.escape(port_id)}" ALIGN="LEFT">{html.escape(label)}</TD></TR>'
            dst_ports_content += '</TABLE>'
        
        # Build SrcPorts column
        src_ports_content = ""
        src_port_items = node_ports.get(node_tag_val, {}).get('src', {})
        sorted_src_ports = sorted(src_port_items.items(), key=lambda item: item[1].lower())
        if sorted_src_ports:
            src_ports_content = '<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="1">' # Changed CELLBORDER to 1
            for port_id, label in sorted_src_ports:
                src_ports_content += f'<TR><TD PORT="{html.escape(port_id)}" ALIGN="RIGHT">{html.escape(label)}</TD></TR>'
            src_ports_content += '</TABLE>'

        # Main node label table
        node_label_html = f'''<
        <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" BGCOLOR="white">
          <TR>
            <TD BORDER="1" WIDTH="40">{dst_ports_content}</TD>
            <TD BGCOLOR="{node_bg_color}" ALIGN="CENTER">
              {center_content}
            </TD>
            <TD BORDER="1" WIDTH="40">{src_ports_content}</TD>
          </TR>
        </TABLE>
        >'''
        
        # Node attributes: shape=plain is key for HTML-like labels to work as rectangles
        # Temporarily simplify label for debugging
        node_definitions.append(f'  "{node_tag_val}" [label={node_label_html}, shape=plain];')

    dot_edges = []
    # Define edges with simplified labels
    if collapse_mode:
        for (src_tag, dst_tag, group_label), rows in grouped_entries.items():
            if not src_tag or not dst_tag:
                continue
            src_port_id = sanitize_port_identifier(group_label, "out")
            dst_port_id = sanitize_port_identifier(group_label, "in")
            count = len(rows)
            edge_label = f"{html.escape(group_label)} ({count})"
            edge_color_value = ""
            if color_edges_by_protocol and collapse_strategy == "protocol":
                edge_color_value = get_protocol_color(group_label)
            edge_attributes = [f'label="{edge_label}"']
            if edge_color_value:
                edge_attributes.append(f'color="{edge_color_value}"')
                edge_attributes.append(f'fontcolor="{edge_color_value}"')
            attr_text = " [" + ", ".join(edge_attributes) + "]"
            from_port = f'"{src_tag}":"{src_port_id}"'
            to_port = f'"{dst_tag}":"{dst_port_id}"'
            dot_edges.append(f'  {from_port} -> {to_port}{attr_text};')
    else:
        for _, row in filtered_cables.iterrows():
            src_tag = str(row["SrcTag"])
            dst_tag = str(row["DstTag"])
            cable_tag = str(row["Tag"])
            cable_type = str(row["Type"])
            src_port = str(row["SrcPort"])
            dst_port = str(row["DstPort"])

            if src_tag != "" and dst_tag != "":
                label_parts = []
                for field_key in edge_fields:
                    value = get_edge_field_value(row, field_key)
                    if value:
                        label_parts.append(value)
                edge_label = "\\n".join(label_parts) if label_parts else ""
                edge_color_value = ""
                if color_edges_by_protocol:
                    edge_color_value = get_protocol_color(row.get("Protocol"))
                edge_attributes = []
                if edge_label:
                    edge_attributes.append(f'label="{edge_label}"')
                if edge_color_value:
                    edge_attributes.append(f'color="{edge_color_value}"')
                    edge_attributes.append(f'fontcolor="{edge_color_value}"')

                from_port = f'"{src_tag}":"{html.escape(src_port)}"' if src_port != "" else f'"{src_tag}"'
                to_port = f'"{dst_tag}":"{html.escape(dst_port)}"' if dst_port != "" else f'"{dst_tag}"'
                attr_text = ""
                if edge_attributes:
                    attr_text = " [" + ", ".join(edge_attributes) + "]"
                dot_edges.append(f'  {from_port} -> {to_port}{attr_text};')

    dot_string = "digraph G {\n  rankdir=LR;\n  node [fontsize=10];\n  edge [fontsize=8];\n" # Added rankdir and default font sizes
    dot_string += "\n".join(node_definitions)
    dot_string += "\n"
    dot_string += "\n".join(dot_edges)
    dot_string += "\n}"
    return dot_string


@app.get("/assets/search", response_model=List[Dict[str, str]])
async def search_assets(
    asset_tag: Optional[str] = None,
    manufacturer: Optional[str] = None,
    model: Optional[str] = None,
):
    """
    Search for assets by asset tag, manufacturer, or model.
    """
    filtered_assets = df_assets.copy()

    if asset_tag:
        filtered_assets = filtered_assets[
            filtered_assets["AssetTag"].str.contains(asset_tag, case=False, na=False)
        ]
    if manufacturer:
        filtered_assets = filtered_assets[
            filtered_assets["Manufacturer"].str.contains(manufacturer, case=False, na=False)
        ]
    if model:
        filtered_assets = filtered_assets[
            filtered_assets["Model"].str.contains(model, case=False, na=False)
        ]

    filtered_assets = filtered_assets.drop(columns=["AssetTagNorm"], errors="ignore")
    processed_assets = clean_dataframe_for_json(filtered_assets)
    return processed_assets.to_dict(orient="records")


@app.get("/assets/tags")
async def list_asset_tags():
    """Returns the list of known asset tags for dropdowns/selections."""
    tags = sorted(
        [canonical_display_tag(tag) for tag in VALID_ASSET_TAGS_NORMALIZED],
        key=lambda value: value.lower(),
    )
    return {"tags": tags}


@app.get("/assets/linked")
async def get_linked_assets(tag: str, direction: str = "outbound"):
    """Returns the list of directly connected assets for the given tag."""
    norm = normalize_tag_value(tag)
    if not norm:
        raise HTTPException(status_code=400, detail="Asset tag is required.")
    if norm not in ALL_KNOWN_TAGS_NORMALIZED:
        raise HTTPException(status_code=404, detail=f"Unknown asset tag: {tag}")

    direction_value = direction.lower()
    if direction_value not in {"inbound", "outbound", "both"}:
        raise HTTPException(status_code=400, detail="Direction must be inbound, outbound, or both.")

    peers: Set[str] = set()
    if direction_value in {"outbound", "both"}:
        outbound_rows = df_cables[df_cables["SrcTagNorm"] == norm]
        for raw in outbound_rows["DstTag"].tolist():
            canonical = canonical_display_tag(raw)
            if canonical:
                peers.add(canonical)
    if direction_value in {"inbound", "both"}:
        inbound_rows = df_cables[df_cables["DstTagNorm"] == norm]
        for raw in inbound_rows["SrcTag"].tolist():
            canonical = canonical_display_tag(raw)
            if canonical:
                peers.add(canonical)

    sorted_peers = sorted(peers, key=lambda value: value.lower())
    return {
        "tag": canonical_display_tag(tag),
        "direction": direction_value,
        "peers": sorted_peers,
    }


@app.get("/cables/filter", response_model=CableFilterResponse)
async def filter_cables(
    target_tag: str,
    direction: str = "both",  # "in", "out", "both"
    cable_type: Optional[str] = None,
    protocol: Optional[str] = None,
    visible_asset_tags: Optional[str] = Query(None), # Comma-separated string
    additional_asset_tags: Optional[str] = Query(None), # New: Comma-separated string
    expansions: Optional[str] = Query(None), # Node expansion directives
    node_fields: Optional[str] = Query(None),
    edge_fields: Optional[str] = Query(None),
):
    """
    Filter cables based on a target asset tag, direction, optional cable type,
    an optional list of visible asset tags, and an optional list of additional asset tags.
    """

    if direction not in ["in", "out", "both"]:
        raise HTTPException(status_code=400, detail="Direction must be 'in', 'out', or 'both'.")

    target_norm = normalize_tag_value(target_tag)
    if not target_norm:
        raise HTTPException(status_code=400, detail="Target asset tag is required.")

    expansion_value = expansions if isinstance(expansions, str) else (expansions or "")
    expansion_map = parse_expansion_param(expansion_value, direction, target_norm)
    broadly_involved_asset_tags_norm: Set[str] = set(expansion_map.keys())

    if visible_asset_tags:
        visible_norm_list = normalize_tag_list(visible_asset_tags)
        broadly_involved_asset_tags_norm.update(visible_norm_list)
    
    if additional_asset_tags:
        additional_norm_list = normalize_tag_list(additional_asset_tags)
        invalid_tags = [tag for tag in additional_norm_list if tag not in ALL_KNOWN_TAGS_NORMALIZED]
        if invalid_tags:
            display_invalid = [canonical_display_tag(tag) for tag in invalid_tags]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid additional asset tags: {', '.join(display_invalid)}. Please check your input.",
            )
        broadly_involved_asset_tags_norm.update(additional_norm_list)

    # Discover cables that touch any of the broadly involved assets so we do not
    # prematurely drop legitimate rows.
    candidate_mask = (
        df_cables["SrcTagNorm"].isin(broadly_involved_asset_tags_norm) |
        df_cables["DstTagNorm"].isin(broadly_involved_asset_tags_norm)
    )
    discovered_cables = df_cables[candidate_mask].copy()

    # Apply expansion directives relative to each specified node.
    expansion_frames = []
    for node_norm, dirs in expansion_map.items():
        subset_frames = []
        if "in" in dirs:
            subset_frames.append(discovered_cables[discovered_cables["DstTagNorm"] == node_norm])
        if "out" in dirs:
            subset_frames.append(discovered_cables[discovered_cables["SrcTagNorm"] == node_norm])
        if subset_frames:
            expansion_frames.append(pd.concat(subset_frames))

    if expansion_frames:
        candidate_cables = pd.concat(expansion_frames).drop_duplicates()
    else:
        candidate_cables = discovered_cables.iloc[0:0].copy()

    # Apply cable type filtering
    if cable_type:
        candidate_cables = candidate_cables[
            candidate_cables["Type"].str.contains(cable_type, case=False, na=False)
        ]
    if protocol:
        candidate_cables = candidate_cables[
            candidate_cables["Protocol"].str.contains(protocol, case=False, na=False)
        ]

    # If we were given an explicit visible set, only include cables whose endpoints are visible.
    if visible_asset_tags:
        visible_tags_set = set(normalize_tag_list(visible_asset_tags))
        candidate_cables = candidate_cables[
            (candidate_cables["SrcTagNorm"].isin(visible_tags_set)) &
            (candidate_cables["DstTagNorm"].isin(visible_tags_set))
        ]

    discovered_asset_tags: Set[str] = set()
    for raw_tag in candidate_cables["SrcTag"].tolist():
        canonical = canonical_display_tag(raw_tag)
        if canonical:
            discovered_asset_tags.add(canonical)
    for raw_tag in candidate_cables["DstTag"].tolist():
        canonical = canonical_display_tag(raw_tag)
        if canonical:
            discovered_asset_tags.add(canonical)
    discovered_asset_tags.update(denormalize_tags(broadly_involved_asset_tags_norm))

    # Canonicalize Src/Dst tags for downstream consumers (tables, diagram parsing).
    candidate_cables["SrcTag"] = candidate_cables["SrcTag"].apply(canonical_display_tag)
    candidate_cables["DstTag"] = candidate_cables["DstTag"].apply(canonical_display_tag)

    cleaned_asset_tags = sorted(
        [tag for tag in (str(t).strip() for t in discovered_asset_tags) if tag],
        key=lambda x: x.lower()
    )

    candidate_cables = candidate_cables.drop(columns=["SrcTagNorm", "DstTagNorm"], errors="ignore")
    processed_cables = clean_dataframe_for_json(candidate_cables)
    return {
        "cables": processed_cables.to_dict(orient="records"),
        "asset_tags": cleaned_asset_tags,
        "primary_target": canonical_display_tag(target_tag),
    }


@app.get("/graphviz/dot")
async def get_graphviz_dot(
    target_tag: str,
    direction: str = "both",
    cable_type: Optional[str] = None,
    protocol: Optional[str] = None,
    visible_asset_tags: Optional[str] = Query(None), # Comma-separated string
    additional_asset_tags: Optional[str] = Query(None), # New: Comma-separated string
    expansions: Optional[str] = Query(None), # Node expansion directives
    node_fields: Optional[str] = Query(None), # Comma-separated node label fields
    edge_fields: Optional[str] = Query(None), # Comma-separated edge label fields
    color_nodes_by_category: bool = Query(False),
    color_edges_by_protocol: bool = Query(False),
    collapse_strategy: Optional[str] = Query("none"),
):
    """
    Generates a Graphviz DOT string for filtered cables and assets.
    """
    # TEMPORARY: Return hardcoded SVG for debugging
    # return Response(content='<svg width="100" height="100"><circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" /></svg>', media_type="image/svg+xml")

    target_norm = normalize_tag_value(target_tag)
    if not target_norm:
        raise HTTPException(status_code=400, detail="Target asset tag is required.")

    expansion_value = expansions if isinstance(expansions, str) else (expansions or "")
    expansion_map = parse_expansion_param(expansion_value, direction, target_norm)
    selected_node_fields = parse_field_selection(node_fields, NODE_FIELD_OPTIONS, DEFAULT_NODE_FIELDS)
    selected_edge_fields = parse_field_selection(edge_fields, EDGE_FIELD_OPTIONS, DEFAULT_EDGE_FIELDS)
    broadly_involved_asset_tags_norm = set(expansion_map.keys())
    if additional_asset_tags:
        additional_tags_list = normalize_tag_list(additional_asset_tags if isinstance(additional_asset_tags, str) else str(additional_asset_tags))
        invalid_tags = [tag for tag in additional_tags_list if tag not in ALL_KNOWN_TAGS_NORMALIZED]
        if invalid_tags:
            display_invalid = [canonical_display_tag(tag) for tag in invalid_tags]
            raise HTTPException(status_code=400, detail=f"Invalid additional asset tags: {', '.join(display_invalid)}. Please check your input.")
        broadly_involved_asset_tags_norm.update(additional_tags_list)

    # Step 2: Discover all cables connected to the `broadly_involved_asset_tags`
    discovered_cables = df_cables[
        (df_cables["SrcTagNorm"].isin(broadly_involved_asset_tags_norm)) |
        (df_cables["DstTagNorm"].isin(broadly_involved_asset_tags_norm))
    ].copy()

    # Step 3: Apply direction and cable_type filters based on expansion directives
    expansion_frames = []
    for node_norm, dirs in expansion_map.items():
        subset_frames = []
        if "in" in dirs:
            subset_frames.append(discovered_cables[discovered_cables["DstTagNorm"] == node_norm])
        if "out" in dirs:
            subset_frames.append(discovered_cables[discovered_cables["SrcTagNorm"] == node_norm])
        if subset_frames:
            expansion_frames.append(pd.concat(subset_frames))

    if expansion_frames:
        candidate_cables = pd.concat(expansion_frames).drop_duplicates()
    else:
        candidate_cables = discovered_cables.iloc[0:0].copy()

    if cable_type:
        candidate_cables = candidate_cables[
            candidate_cables["Type"].str.contains(cable_type, case=False, na=False)
        ]
    if protocol:
        candidate_cables = candidate_cables[
            candidate_cables["Protocol"].str.contains(protocol, case=False, na=False)
        ]
    
    # Step 4: Determine the *final* set of nodes to render (normalized to avoid case duplicates)
    candidate_src_norm = set(candidate_cables["SrcTagNorm"]) if "SrcTagNorm" in candidate_cables else set()
    candidate_dst_norm = set(candidate_cables["DstTagNorm"]) if "DstTagNorm" in candidate_cables else set()
    all_candidate_nodes_norm = {tag for tag in candidate_src_norm.union(candidate_dst_norm) if tag}
    all_candidate_nodes_norm.update(broadly_involved_asset_tags_norm) # Include isolated additional assets

    if visible_asset_tags:
        user_visible_norm = set(normalize_tag_list(visible_asset_tags))
        final_nodes_norm = all_candidate_nodes_norm.intersection(user_visible_norm)
    else:
        final_nodes_norm = set(all_candidate_nodes_norm)

    final_nodes_norm.update(expansion_map.keys())
    final_nodes_norm = {tag for tag in final_nodes_norm if tag}
    final_nodes_to_render = denormalize_tags(final_nodes_norm)

    # Build the final set of cables to render by looking at every cable between the selected nodes.
    filtered_cables = df_cables[
        (df_cables["SrcTagNorm"].isin(final_nodes_norm)) &
        (df_cables["DstTagNorm"].isin(final_nodes_norm))
    ].copy()

    # Canonicalize tag casing for all rendered edges/nodes.
    filtered_cables["SrcTag"] = filtered_cables["SrcTag"].apply(canonical_display_tag)
    filtered_cables["DstTag"] = filtered_cables["DstTag"].apply(canonical_display_tag)

    # Respect cable_type filtering on the rendered edges as well.
    if cable_type:
        filtered_cables = filtered_cables[
            filtered_cables["Type"].str.contains(cable_type, case=False, na=False)
        ]
    if protocol:
        filtered_cables = filtered_cables[
            filtered_cables["Protocol"].str.contains(protocol, case=False, na=False)
        ]
    if protocol:
        filtered_cables = filtered_cables[
            filtered_cables["Protocol"].str.contains(protocol, case=False, na=False)
        ]

    # Handle truly empty graph (no nodes to render)
    if not final_nodes_to_render:
        empty_dot_string = "digraph G { label=\"No assets found to display.\"; labelloc=\"t\"; }"
        try:
            dot_source = graphviz.Source(empty_dot_string)
            svg_output = dot_source.pipe(format='svg').decode('utf-8')
            return Response(content=svg_output, media_type="image/svg+xml")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error rendering empty graph SVG: {e}")
    
    # graph_assets will contain full details for all `final_nodes_to_render`
    graph_assets = df_assets[df_assets["AssetTag"].isin(final_nodes_to_render)]
    
    # Call generate_dot_string with the *explicitly requested* nodes to render and their filtered cables
    collapse_value = (collapse_strategy or "none").lower()
    if collapse_value not in COLLAPSE_OPTIONS:
        raise HTTPException(status_code=400, detail="Invalid collapse strategy. Choose none, protocol, or type.")

    dot_string = generate_dot_string(
        filtered_cables,
        graph_assets,
        final_nodes_to_render,
        selected_node_fields,
        selected_edge_fields,
        color_nodes_by_category,
        color_edges_by_protocol,
        collapse_value,
    ) 

    # Try rendering the DOT string to SVG
    try:
        dot_source = graphviz.Source(dot_string) # Create a Graphviz Source object
        svg_output = dot_source.pipe(format='svg').decode('utf-8') # Render to SVG and decode
        return Response(content=svg_output, media_type="image/svg+xml") # Return as SVG
    except Exception as e:
        print(f"Error rendering Graphviz DOT to SVG: {e}")
        # If rendering fails, return a 500 error
        raise HTTPException(status_code=500, detail=f"Error rendering Graphviz SVG: {e}")


@app.get("/crosspoint/matrix")
async def get_crosspoint_matrix(
    source_tag: str,
    target_tag: str,
    header_fields: Optional[str] = Query(None),
    protocol: Optional[str] = Query(None),
):
    source_norm = normalize_tag_value(source_tag)
    target_norm = normalize_tag_value(target_tag)
    if not source_norm or not target_norm:
        raise HTTPException(status_code=400, detail="Source and Target asset tags are required.")
    if source_norm not in ALL_KNOWN_TAGS_NORMALIZED:
        raise HTTPException(status_code=404, detail=f"Unknown source asset tag: {source_tag}")
    if target_norm not in ALL_KNOWN_TAGS_NORMALIZED:
        raise HTTPException(status_code=404, detail=f"Unknown target asset tag: {target_tag}")

    selected_fields = parse_field_selection(header_fields, CROSSPOINT_HEADER_FIELDS, CROSSPOINT_DEFAULT_FIELDS)
    base_pairs = df_cables[
        (df_cables["SrcTagNorm"] == source_norm) &
        (df_cables["DstTagNorm"] == target_norm)
    ].copy()

    protocol_display_map: Dict[str, str] = {}
    for raw_value in base_pairs["Protocol"]:
        text = format_display_value(raw_value)
        if not text:
            continue
        canon = text.lower()
        if canon not in protocol_display_map:
            protocol_display_map[canon] = text

    selected_protocol = format_display_value(protocol).lower()
    if selected_protocol and selected_protocol not in protocol_display_map:
        protocol_display_map[selected_protocol] = protocol.upper() if protocol else selected_protocol.upper()

    # Prepare canonical port columns for consistent matching
    base_pairs = base_pairs.assign(
        SrcPortSafe=base_pairs["SrcPort"].apply(normalize_port_value),
        DstPortSafe=base_pairs["DstPort"].apply(normalize_port_value),
    )

    row_ports = sorted({value for value in base_pairs["SrcPortSafe"]})
    column_ports = sorted({value for value in base_pairs["DstPortSafe"]})

    row_groups: Dict[str, pd.DataFrame] = {
        str(port): group for port, group in base_pairs.groupby("SrcPortSafe")
    }
    col_groups: Dict[str, pd.DataFrame] = {
        str(port): group for port, group in base_pairs.groupby("DstPortSafe")
    }

    connection_map: Dict[Tuple[str, str], Set[str]] = {}
    for _, row in base_pairs.iterrows():
        key = (row["SrcPortSafe"], row["DstPortSafe"])
        proto = format_display_value(row.get("Protocol"))
        canon_proto = proto.lower() if proto else ""
        if key not in connection_map:
            connection_map[key] = set()
        connection_map[key].add(canon_proto)

    empty_subset = base_pairs.iloc[0:0]
    rows_payload = [
        {
            "port": port,
            "label": build_crosspoint_label(port, row_groups.get(port, empty_subset), selected_fields),
        }
        for port in row_ports
    ]
    columns_payload = [
        {
            "port": port,
            "label": build_crosspoint_label(port, col_groups.get(port, empty_subset), selected_fields),
        }
        for port in column_ports
    ]

    matrix: List[List[bool]] = []
    if row_ports and column_ports:
        for row_port in row_ports:
            row_values: List[bool] = []
            for col_port in column_ports:
                proto_set = connection_map.get((row_port, col_port), set())
                if not proto_set:
                    row_values.append(False)
                elif not selected_protocol:
                    row_values.append(True)
                else:
                    row_values.append(selected_protocol in proto_set)
            matrix.append(row_values)

    protocol_options = [{"value": "", "label": "All Protocols"}]
    for canon, display in sorted(protocol_display_map.items(), key=lambda item: item[1].lower()):
        protocol_options.append({
            "value": canon,
            "label": display,
        })

    return {
        "source_tag": canonical_display_tag(source_tag),
        "target_tag": canonical_display_tag(target_tag),
        "header_fields": selected_fields,
        "protocol": selected_protocol,
        "protocols": protocol_options,
        "rows": rows_payload,
        "columns": columns_payload,
        "matrix": matrix,
    }
