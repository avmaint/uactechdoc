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
        df_cables["Tag"] = df_cables["Tag"].astype(str).str.strip()
        df_cables["SrcTag"] = df_cables["SrcTag"].astype(str).str.strip()
        df_cables["DstTag"] = df_cables["DstTag"].astype(str).str.strip()
        df_cables["TagNorm"] = df_cables["Tag"].str.upper()
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
CABLE_RECORD_TAG_LOOKUP: Dict[str, str] = {}
ALL_KNOWN_TAGS_NORMALIZED: Set[str] = set()
VALID_CABLE_IDS_NORMALIZED: Set[str] = set()
JUNCTION_NODE_PREFIX = "__cable_junction__::"

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
    global ASSET_TAG_LOOKUP, VALID_ASSET_TAGS_NORMALIZED, CABLE_TAG_LOOKUP
    global CABLE_RECORD_TAG_LOOKUP, ALL_KNOWN_TAGS_NORMALIZED, VALID_CABLE_IDS_NORMALIZED
    ASSET_TAG_LOOKUP = dict(zip(df_assets["AssetTagNorm"], df_assets["AssetTag"]))
    VALID_ASSET_TAGS_NORMALIZED = set(ASSET_TAG_LOOKUP.keys())

    CABLE_RECORD_TAG_LOOKUP = {}
    for tag in df_cables["Tag"].dropna():
        norm = normalize_tag_value(tag)
        if norm and norm not in CABLE_RECORD_TAG_LOOKUP:
            CABLE_RECORD_TAG_LOOKUP[norm] = str(tag).strip()
    VALID_CABLE_IDS_NORMALIZED = set(CABLE_RECORD_TAG_LOOKUP.keys())

    CABLE_TAG_LOOKUP = {}
    for tag in pd.concat([df_cables["Tag"], df_cables["SrcTag"], df_cables["DstTag"]]).dropna():
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


def is_cable_record_tag(tag_value: Optional[str]) -> bool:
    return normalize_tag_value(tag_value) in VALID_CABLE_IDS_NORMALIZED


def is_asset_tag(tag_value: Optional[str]) -> bool:
    return normalize_tag_value(tag_value) in VALID_ASSET_TAGS_NORMALIZED


def build_junction_node_id(current_cable_tag: Optional[str], referenced_cable_tag: Optional[str]) -> str:
    pair = sorted([
        normalize_tag_value(current_cable_tag),
        normalize_tag_value(referenced_cable_tag),
    ])
    return JUNCTION_NODE_PREFIX + "::".join([part for part in pair if part])


def is_junction_node_id(node_id: str) -> bool:
    return str(node_id).startswith(JUNCTION_NODE_PREFIX)


def resolve_query_target(target_tag: Optional[str], cable_id: Optional[str]) -> Tuple[str, str]:
    target_norm = normalize_tag_value(target_tag)
    cable_norm = normalize_tag_value(cable_id)

    if target_norm and target_norm in ALL_KNOWN_TAGS_NORMALIZED:
        return target_norm, canonical_display_tag(target_norm)
    if target_norm and target_norm in VALID_CABLE_IDS_NORMALIZED:
        return target_norm, canonical_display_tag(target_norm)
    if cable_norm and cable_norm in VALID_CABLE_IDS_NORMALIZED:
        return cable_norm, canonical_display_tag(cable_norm)

    if target_norm or cable_norm:
        unresolved = target_norm or cable_norm
        raise HTTPException(status_code=404, detail=f"Unknown asset tag or cable ID: {unresolved}")

    raise HTTPException(status_code=400, detail="Target asset tag or cable ID is required.")


def rows_for_expansion_target(node_norm: str, directions: Set[str]) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    if is_cable_record_tag(node_norm):
        frames.append(df_cables[df_cables["TagNorm"] == node_norm])
    if "in" in directions:
        frames.append(df_cables[df_cables["DstTagNorm"] == node_norm])
    if "out" in directions:
        frames.append(df_cables[df_cables["SrcTagNorm"] == node_norm])
    if not frames:
        return df_cables.iloc[0:0].copy()
    return pd.concat(frames).drop_duplicates()


def expand_cable_reference_closure(seed_rows: pd.DataFrame) -> pd.DataFrame:
    if seed_rows.empty:
        return seed_rows.copy()

    expanded = seed_rows.copy()
    processed_refs: Set[str] = set()

    while True:
        endpoint_refs = (
            set(expanded["SrcTagNorm"].dropna().tolist()) |
            set(expanded["DstTagNorm"].dropna().tolist())
        ) & VALID_CABLE_IDS_NORMALIZED
        pending_refs = endpoint_refs - processed_refs
        if not pending_refs:
            break
        processed_refs.update(pending_refs)
        new_rows = df_cables[df_cables["TagNorm"].isin(pending_refs)]
        if new_rows.empty:
            continue
        expanded = pd.concat([expanded, new_rows]).drop_duplicates()

    return expanded


def build_candidate_cables(expansion_map: Dict[str, Set[str]]) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for node_norm, dirs in expansion_map.items():
        subset = rows_for_expansion_target(node_norm, dirs)
        if not subset.empty:
            frames.append(subset)
    if not frames:
        return df_cables.iloc[0:0].copy()
    return expand_cable_reference_closure(pd.concat(frames).drop_duplicates())


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
    excluded_cable_columns = {"TagNorm", "SrcTagNorm", "DstTagNorm"}
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

# Helper function to get connection details (inputs or outputs)
def _get_device_connections_details(target_norm: str, is_input: bool) -> List[Dict[str, str]]:
    if is_input:
        # For inputs, the target is the destination of the cable
        cables_filtered = df_cables[df_cables["DstTagNorm"] == target_norm].copy()
        partner_tag_col = "SrcTagNorm"
        target_port_col = "DstPort"
        partner_port_col = "SrcPort"
    else:
        # For outputs, the target is the source of the cable
        cables_filtered = df_cables[df_cables["SrcTagNorm"] == target_norm].copy()
        partner_tag_col = "DstTagNorm"
        target_port_col = "SrcPort"
        partner_port_col = "DstPort"

    if cables_filtered.empty:
        return []

    # Filter out junction nodes when identifying partner assets
    partner_assets_tags_norm = cables_filtered[partner_tag_col][
        ~cables_filtered[partner_tag_col].apply(is_cable_record_tag)
    ].unique()

    # Get details for partner assets
    partner_assets_details = df_assets[
        df_assets["AssetTagNorm"].isin(partner_assets_tags_norm)
    ].set_index("AssetTagNorm")

    results = []
    for _, cable_row in cables_filtered.iterrows():
        partner_norm = cable_row[partner_tag_col]
        
        # Determine partner details. If it's a junction node, use generic info.
        if is_cable_record_tag(partner_norm):
            partner_details: Dict[str, Any] = { # Explicitly type as Dict[str, Any]
                "Manufacturer": "N/A",
                "Model": "Cable Junction",
                "Usage": "Internal Cable Splice"
            }
            # For display, junction nodes might use a generated ID
            partner_display_tag = f"JUNCTION_{canonical_display_tag(cable_row['Tag'])}" 
        else:
            partner_details = partner_assets_details.loc[partner_norm].to_dict() if partner_norm in partner_assets_details.index else {}
            partner_display_tag = canonical_display_tag(partner_norm)
        
        result_row = {
            "TargetPort": format_display_value(cable_row[target_port_col]),
            ("SourcePort" if is_input else "DestinationPort"): format_display_value(cable_row[partner_port_col]),
            "Protocol": format_display_value(cable_row["Protocol"]),
            "CableID": canonical_display_tag(cable_row["Tag"]),
            "PartnerAssetTag": partner_display_tag,
            "PartnerManufacturer": format_display_value(partner_details.get("Manufacturer")),
            "PartnerModel": format_display_value(partner_details.get("Model")),
            "PartnerUsage": format_display_value(partner_details.get("Usage")),
        }
        results.append(result_row)
    
    # Clean the DataFrame before converting to dicts to handle JSON serialization
    # Ensure results_df is created only if results is not empty
    if results:
        results_df = pd.DataFrame(results)
        results_df = clean_dataframe_for_json(results_df)
        return results_df.to_dict(orient="records")
    return []


@app.get("/diagram/connections/inputs")
async def get_diagram_input_connections(target_tag: str) -> List[Dict[str, str]]:
    """
    Returns input connection details for a given target asset tag.
    Includes partner device details (manufacturer, model, usage).
    """
    target_norm = normalize_tag_value(target_tag)
    if not target_norm or target_norm not in VALID_ASSET_TAGS_NORMALIZED:
        raise HTTPException(status_code=404, detail=f"Target asset tag not found: {target_tag}")
    
    return _get_device_connections_details(target_norm, is_input=True)

@app.get("/diagram/connections/outputs")
async def get_diagram_output_connections(target_tag: str) -> List[Dict[str, str]]:
    """
    Returns output connection details for a given target asset tag.
    Includes partner device details (manufacturer, model, usage).
    """
    target_norm = normalize_tag_value(target_tag)
    if not target_norm or target_norm not in VALID_ASSET_TAGS_NORMALIZED:
        raise HTTPException(status_code=404, detail=f"Target asset tag not found: {target_tag}")
    
    return _get_device_connections_details(target_norm, is_input=False)


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
    collapse_mode = collapse_strategy in {"protocol", "type"}
    dot_nodes: Set[str] = set()
    asset_nodes = {str(tag).strip() for tag in all_nodes_to_render if str(tag).strip()}
    node_ports: Dict[str, Dict[str, Dict[str, str]]] = {
        node_tag: {"src": {}, "dst": {}} for node_tag in asset_nodes
    }

    graph_edges: List[Dict[str, object]] = []

    def resolve_endpoint(row: pd.Series, side: str) -> Tuple[str, str, bool]:
        cable_tag = normalize_tag_value(row.get("Tag"))
        endpoint_tag = normalize_tag_value(row.get("SrcTag" if side == "src" else "DstTag"))
        endpoint_display = canonical_display_tag(endpoint_tag)
        port_value = normalize_asset_field_value(row.get("SrcPort" if side == "src" else "DstPort", ""))
        if endpoint_tag and endpoint_tag in VALID_CABLE_IDS_NORMALIZED:
            return build_junction_node_id(cable_tag, endpoint_tag), port_value, True
        return endpoint_display, port_value, False

    for _, row in filtered_cables.iterrows():
        src_node, src_port, src_is_junction = resolve_endpoint(row, "src")
        dst_node, dst_port, dst_is_junction = resolve_endpoint(row, "dst")
        if not src_node or not dst_node:
            continue
        graph_edges.append({
            "src_node": src_node,
            "dst_node": dst_node,
            "src_port": src_port,
            "dst_port": dst_port,
            "src_is_junction": src_is_junction,
            "dst_is_junction": dst_is_junction,
            "row": row,
        })
        dot_nodes.add(src_node)
        dot_nodes.add(dst_node)
        if not src_is_junction:
            node_ports.setdefault(src_node, {"src": {}, "dst": {}})
        if not dst_is_junction:
            node_ports.setdefault(dst_node, {"src": {}, "dst": {}})

    dot_nodes.update(asset_nodes)

    if collapse_mode:
        grouped_entries: Dict[Tuple[str, str, str], List[Dict[str, object]]] = {}
        for edge in graph_edges:
            row = edge["row"]
            group_label = collapse_label_for_row(row, collapse_strategy)
            key = (str(edge["src_node"]), str(edge["dst_node"]), group_label)
            grouped_entries.setdefault(key, []).append(edge)

        for (src_node, dst_node, group_label), edges in grouped_entries.items():
            if src_node in node_ports:
                node_ports[src_node]["src"][sanitize_port_identifier(group_label, "out")] = group_label
            if dst_node in node_ports:
                node_ports[dst_node]["dst"][sanitize_port_identifier(group_label, "in")] = group_label
    else:
        for edge in graph_edges:
            if edge["src_node"] in node_ports and edge["src_port"]:
                node_ports[str(edge["src_node"])]["src"][str(edge["src_port"])] = str(edge["src_port"])
            if edge["dst_node"] in node_ports and edge["dst_port"]:
                node_ports[str(edge["dst_node"])]["dst"][str(edge["dst_port"])] = str(edge["dst_port"])

    assets_by_tag = {
        row["AssetTag"]: row.to_dict()
        for _, row in assets_df.iterrows()
        if row.get("AssetTag")
    }

    node_definitions = []
    for node_tag_val in sorted(dot_nodes):
        if is_junction_node_id(node_tag_val):
            node_definitions.append(
                f'  "{node_tag_val}" [shape=point, width=0.14, height=0.14, label="", xlabel="", tooltip="Cable splice/junction"];'
            )
            continue

        asset_record = assets_by_tag.get(node_tag_val, {})
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

        dst_ports_content = ""
        dst_port_items = node_ports.get(node_tag_val, {}).get("dst", {})
        sorted_dst_ports = sorted(dst_port_items.items(), key=lambda item: item[1].lower())
        if sorted_dst_ports:
            dst_ports_content = '<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="1">'
            for port_id, label in sorted_dst_ports:
                dst_ports_content += f'<TR><TD PORT="{html.escape(port_id)}" ALIGN="LEFT">{html.escape(label)}</TD></TR>'
            dst_ports_content += "</TABLE>"

        src_ports_content = ""
        src_port_items = node_ports.get(node_tag_val, {}).get("src", {})
        sorted_src_ports = sorted(src_port_items.items(), key=lambda item: item[1].lower())
        if sorted_src_ports:
            src_ports_content = '<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="1">'
            for port_id, label in sorted_src_ports:
                src_ports_content += f'<TR><TD PORT="{html.escape(port_id)}" ALIGN="RIGHT">{html.escape(label)}</TD></TR>'
            src_ports_content += "</TABLE>"

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
        node_definitions.append(f'  "{node_tag_val}" [label={node_label_html}, shape=plain];')

    dot_edges = []
    if collapse_mode:
        for (src_node, dst_node, group_label), edges in grouped_entries.items():
            if not src_node or not dst_node:
                continue
            src_port_id = sanitize_port_identifier(group_label, "out")
            dst_port_id = sanitize_port_identifier(group_label, "in")
            count = len(edges)
            edge_label = f"{html.escape(group_label)} ({count})"
            edge_color_value = ""
            if color_edges_by_protocol and collapse_strategy == "protocol":
                edge_color_value = get_protocol_color(group_label)
            edge_attributes = [f'label="{edge_label}"']
            if edge_color_value:
                edge_attributes.append(f'color="{edge_color_value}"')
                edge_attributes.append(f'fontcolor="{edge_color_value}"')
            attr_text = " [" + ", ".join(edge_attributes) + "]"
            from_port = f'"{src_node}":"{src_port_id}"' if src_node in node_ports else f'"{src_node}"'
            to_port = f'"{dst_node}":"{dst_port_id}"' if dst_node in node_ports else f'"{dst_node}"'
            dot_edges.append(f"  {from_port} -> {to_port}{attr_text};")
    else:
        for edge in graph_edges:
            row = edge["row"]
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

            from_port = f'"{edge["src_node"]}":"{html.escape(str(edge["src_port"]))}"' if edge["src_node"] in node_ports and edge["src_port"] else f'"{edge["src_node"]}"'
            to_port = f'"{edge["dst_node"]}":"{html.escape(str(edge["dst_port"]))}"' if edge["dst_node"] in node_ports and edge["dst_port"] else f'"{edge["dst_node"]}"'
            attr_text = ""
            if edge_attributes:
                attr_text = " [" + ", ".join(edge_attributes) + "]"
            dot_edges.append(f"  {from_port} -> {to_port}{attr_text};")

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
    target_tag: Optional[str] = None,
    cable_id: Optional[str] = None,
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

    target_norm, primary_target = resolve_query_target(target_tag, cable_id)

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

    candidate_cables = build_candidate_cables(expansion_map)

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
            (
                candidate_cables["SrcTagNorm"].isin(visible_tags_set) |
                candidate_cables["SrcTagNorm"].isin(VALID_CABLE_IDS_NORMALIZED)
            ) &
            (
                candidate_cables["DstTagNorm"].isin(visible_tags_set) |
                candidate_cables["DstTagNorm"].isin(VALID_CABLE_IDS_NORMALIZED)
            )
        ]

    discovered_asset_tags: Set[str] = set()
    for raw_tag in candidate_cables["SrcTagNorm"].tolist():
        if raw_tag in VALID_CABLE_IDS_NORMALIZED:
            continue
        canonical = canonical_display_tag(raw_tag)
        if canonical:
            discovered_asset_tags.add(canonical)
    for raw_tag in candidate_cables["DstTagNorm"].tolist():
        if raw_tag in VALID_CABLE_IDS_NORMALIZED:
            continue
        canonical = canonical_display_tag(raw_tag)
        if canonical:
            discovered_asset_tags.add(canonical)
    discovered_asset_tags.update({
        canonical_display_tag(tag)
        for tag in broadly_involved_asset_tags_norm
        if is_asset_tag(tag)
    })

    # Canonicalize Src/Dst tags for downstream consumers (tables, diagram parsing).
    candidate_cables["SrcTag"] = candidate_cables["SrcTag"].apply(canonical_display_tag)
    candidate_cables["DstTag"] = candidate_cables["DstTag"].apply(canonical_display_tag)

    cleaned_asset_tags = sorted(
        [tag for tag in (str(t).strip() for t in discovered_asset_tags) if tag],
        key=lambda x: x.lower()
    )

    candidate_cables = candidate_cables.drop(columns=["TagNorm", "SrcTagNorm", "DstTagNorm"], errors="ignore")
    processed_cables = clean_dataframe_for_json(candidate_cables)
    return {
        "cables": processed_cables.to_dict(orient="records"),
        "asset_tags": cleaned_asset_tags,
        "primary_target": primary_target,
    }


@app.get("/graphviz/dot")
async def get_graphviz_dot(
    target_tag: Optional[str] = None,
    cable_id: Optional[str] = None,
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

    target_norm, _ = resolve_query_target(target_tag, cable_id)

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

    candidate_cables = build_candidate_cables(expansion_map)

    if cable_type:
        candidate_cables = candidate_cables[
            candidate_cables["Type"].str.contains(cable_type, case=False, na=False)
        ]
    if protocol:
        candidate_cables = candidate_cables[
            candidate_cables["Protocol"].str.contains(protocol, case=False, na=False)
        ]
    
    visible_norm_set = set(normalize_tag_list(visible_asset_tags)) if visible_asset_tags else set()
    if visible_norm_set:
        filtered_cables = candidate_cables[
            (
                candidate_cables["SrcTagNorm"].isin(visible_norm_set) |
                candidate_cables["SrcTagNorm"].isin(VALID_CABLE_IDS_NORMALIZED)
            ) &
            (
                candidate_cables["DstTagNorm"].isin(visible_norm_set) |
                candidate_cables["DstTagNorm"].isin(VALID_CABLE_IDS_NORMALIZED)
            )
        ].copy()
    else:
        filtered_cables = candidate_cables.copy()

    # Canonicalize tag casing for all rendered edges/nodes.
    filtered_cables["SrcTag"] = filtered_cables["SrcTag"].apply(canonical_display_tag)
    filtered_cables["DstTag"] = filtered_cables["DstTag"].apply(canonical_display_tag)

    candidate_asset_nodes_norm = {
        tag for tag in set(filtered_cables["SrcTagNorm"].tolist()) | set(filtered_cables["DstTagNorm"].tolist())
        if is_asset_tag(tag)
    }
    candidate_asset_nodes_norm.update({tag for tag in broadly_involved_asset_tags_norm if is_asset_tag(tag)})
    if visible_norm_set:
        final_asset_nodes_norm = candidate_asset_nodes_norm.intersection(visible_norm_set)
        final_asset_nodes_norm.update({tag for tag in expansion_map.keys() if is_asset_tag(tag)})
    else:
        final_asset_nodes_norm = candidate_asset_nodes_norm
    final_nodes_to_render = denormalize_tags(final_asset_nodes_norm)

    # Handle truly empty graph (no nodes to render)
    if not final_nodes_to_render and filtered_cables.empty:
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
