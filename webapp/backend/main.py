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
    }

# --- Graphviz DOT Generation Function ---
def generate_dot_string(
    filtered_cables: pd.DataFrame,
    assets_df: pd.DataFrame,
    all_nodes_to_render: Set[str],
    node_fields: List[str],
    edge_fields: List[str],
) -> str:
    """
    Generates a Graphviz DOT string from filtered cable and asset data,
    with custom node shapes and port displays.
    Ensures all specified nodes in `all_nodes_to_render` are included, even if isolated.
    """
    dot_nodes = set(all_nodes_to_render) # Initialize with all nodes that need to be rendered
    node_ports = {node_tag: {'src': set(), 'dst': set()} for node_tag in all_nodes_to_render} # Pre-fill node_ports
    
    # Collect all ports for nodes that have connecting cables
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
            node_ports[src_tag] = {'src': set(), 'dst': set()}
        if dst_tag not in node_ports:
            node_ports[dst_tag] = {'src': set(), 'dst': set()}

        if src_port != "":
            node_ports[src_tag]['src'].add(src_port)

        if dst_port != "":
            node_ports[dst_tag]['dst'].add(dst_port)

    node_definitions = []
    # Define nodes with HTML-like labels for ports and asset info
    for node_tag_val in sorted([str(n) for n in list(dot_nodes)]): # Iterate over all collected nodes
        asset_info = assets_df[assets_df["AssetTag"] == node_tag_val]
        asset_record = asset_info.iloc[0].to_dict() if not asset_info.empty else {}
        display_tag = str(node_tag_val).strip()

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
        sorted_dst_ports = sorted([str(p) for p in list(node_ports.get(node_tag_val, {}).get('dst', set()))])
        if sorted_dst_ports:
            dst_ports_content = '<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="1">' # Changed CELLBORDER to 1
            for port in sorted_dst_ports:
                dst_ports_content += f'<TR><TD PORT="{html.escape(port)}" ALIGN="LEFT">{html.escape(port)}</TD></TR>' # HTML escape port
            dst_ports_content += '</TABLE>'
        
        # Build SrcPorts column
        src_ports_content = ""
        sorted_src_ports = sorted([str(p) for p in list(node_ports.get(node_tag_val, {}).get('src', set()))])
        if sorted_src_ports:
            src_ports_content = '<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="1">' # Changed CELLBORDER to 1
            for port in sorted_src_ports:
                src_ports_content += f'<TR><TD PORT="{html.escape(port)}" ALIGN="RIGHT">{html.escape(port)}</TD></TR>' # HTML escape port
            src_ports_content += '</TABLE>'

        # Main node label table
        node_label_html = f'''<
        <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" BGCOLOR="white">
          <TR>
            <TD BORDER="1" WIDTH="40">{dst_ports_content}</TD>
            <TD BGCOLOR="lightblue" ALIGN="CENTER">
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
    for _, row in filtered_cables.iterrows():
        src_tag = str(row["SrcTag"])
        dst_tag = str(row["DstTag"])
        cable_tag = str(row["Tag"])
        cable_type = str(row["Type"])
        src_port = str(row["SrcPort"])
        dst_port = str(row["DstPort"])

        if src_tag != "" and dst_tag != "": # Cleaned data should have "" instead of None
            label_parts = []
            for field_key in edge_fields:
                value = get_edge_field_value(row, field_key)
                if value:
                    label_parts.append(value)
            edge_label = "\\n".join(label_parts) if label_parts else ""
            
            # Use port names in the edge definition
            # Node:port syntax is used for connecting to specific ports within HTML-like labels
            from_port = f'"{src_tag}":"{html.escape(src_port)}"' if src_port != "" else f'"{src_tag}"'
            to_port = f'"{dst_tag}":"{html.escape(dst_port)}"' if dst_port != "" else f'"{dst_tag}"'
            
            dot_edges.append(f'  {from_port} -> {to_port} [label="{edge_label}"];')

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


@app.get("/cables/filter", response_model=CableFilterResponse)
async def filter_cables(
    target_tag: str,
    direction: str = "both",  # "in", "out", "both"
    cable_type: Optional[str] = None,
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
    visible_asset_tags: Optional[str] = Query(None), # Comma-separated string
    additional_asset_tags: Optional[str] = Query(None), # New: Comma-separated string
    expansions: Optional[str] = Query(None), # Node expansion directives
    node_fields: Optional[str] = Query(None), # Comma-separated node label fields
    edge_fields: Optional[str] = Query(None), # Comma-separated edge label fields
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
    dot_string = generate_dot_string(filtered_cables, graph_assets, final_nodes_to_render, selected_node_fields, selected_edge_fields) 

    # Try rendering the DOT string to SVG
    try:
        dot_source = graphviz.Source(dot_string) # Create a Graphviz Source object
        svg_output = dot_source.pipe(format='svg').decode('utf-8') # Render to SVG and decode
        return Response(content=svg_output, media_type="image/svg+xml") # Return as SVG
    except Exception as e:
        print(f"Error rendering Graphviz DOT to SVG: {e}")
        # If rendering fails, return a 500 error
        raise HTTPException(status_code=500, detail=f"Error rendering Graphviz SVG: {e}")
