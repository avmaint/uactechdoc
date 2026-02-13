import pandas as pd
import numpy as np
import html # Import html module
import graphviz # Import graphviz
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response # Import Response for SVG output
from typing import Optional, List

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
def load_assets_data():
    """Loads asset data from uac_assets.xlsx."""
    try:
        df_assets = pd.read_excel("../data/uac_assets.xlsx", sheet_name="assets")
        # Filter out rows where AssetTag is NaN, as these seem to be summary/non-asset rows
        df_assets = df_assets.dropna(subset=["AssetTag"])
        # Force all columns to object dtype to prevent NaN re-introduction issues
        df_assets = df_assets.astype(object)
        return df_assets
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading asset data: {e}")

def load_cables_data():
    """Loads cable data from uac_cables.xlsx."""
    try:
        df_cables = pd.read_excel("../data/uac_cables.xlsx", sheet_name="Cables")
        # Force all columns to object dtype to prevent NaN re-introduction issues
        df_cables = df_cables.astype(object)
        return df_cables
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading cable data: {e}")

# Load data globally for the application to avoid reloading on each request
df_assets = load_assets_data()
df_cables = load_cables_data()


@app.get("/")
async def read_root():
    return {"message": "Welcome to the UAC Tech Documentation API"}

# --- Graphviz DOT Generation Function ---
def generate_dot_string(filtered_cables: pd.DataFrame, assets_df: pd.DataFrame) -> str: # Renamed function
    """
    Generates a Graphviz DOT string from filtered cable and asset data,
    with custom node shapes and port displays.
    """
    dot_nodes = set()
    node_ports = {} # To store unique src/dst ports for each node

    # Collect all nodes and their associated ports
    for _, row in filtered_cables.iterrows():
        src_tag = str(row["SrcTag"]) # Ensure string
        dst_tag = str(row["DstTag"]) # Ensure string
        src_port = str(row["SrcPort"]) # Ensure string
        dst_port = str(row["DstPort"]) # Ensure string

        if src_tag != "": # Cleaned data should have "" instead of None
            dot_nodes.add(src_tag)
            if src_tag not in node_ports:
                node_ports[src_tag] = {'src': set(), 'dst': set()}
            if src_port != "":
                node_ports[src_tag]['src'].add(src_port)

        if dst_tag != "": # Cleaned data should have "" instead of None
            dot_nodes.add(dst_tag)
            if dst_tag not in node_ports:
                node_ports[dst_tag] = {'src': set(), 'dst': set()}
            if dst_port != "":
                node_ports[dst_tag]['dst'].add(dst_port)

    node_definitions = []
    # Define nodes with HTML-like labels for ports and asset info
    for node_tag_val in sorted([str(n) for n in list(dot_nodes)]): # Ensure node_tag_val is string for sorting
        asset_info = assets_df[assets_df["AssetTag"] == node_tag_val]
        
        # Default labels (empty strings for easier HTML-like label generation)
        display_manufacturer = ""
        display_model = ""
        
        if not asset_info.empty:
            display_manufacturer = asset_info["Manufacturer"].iloc[0]
            display_model = asset_info["Model"].iloc[0]
            
        # Ensure manufacturer and model are properly formatted for HTML-like label
        manufacturer_line = f"<BR/>{html.escape(display_manufacturer)}" if display_manufacturer else ""
        model_line = f"<BR/>{html.escape(display_model)}" if display_model else ""

        # Build DstPorts column
        dst_ports_content = ""
        sorted_dst_ports = sorted([str(p) for p in list(node_ports.get(node_tag_val, {}).get('dst', set()))])
        if sorted_dst_ports:
            # Added CELLBORDER="1" to inner table
            dst_ports_content = '<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="1">'
            for port in sorted_dst_ports:
                dst_ports_content += f'<TR><TD PORT="{html.escape(port)}" ALIGN="LEFT">{html.escape(port)}</TD></TR>' # HTML escape port
            dst_ports_content += '</TABLE>'
        
        # Build SrcPorts column
        src_ports_content = ""
        sorted_src_ports = sorted([str(p) for p in list(node_ports.get(node_tag_val, {}).get('src', set()))])
        if sorted_src_ports:
            # Added CELLBORDER="1" to inner table
            src_ports_content = '<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="1">'
            for port in sorted_src_ports:
                src_ports_content += f'<TR><TD PORT="{html.escape(port)}" ALIGN="RIGHT">{html.escape(port)}</TD></TR>' # HTML escape port
            src_ports_content += '</TABLE>'

        # Main node label table
        node_label_html = f'''<
        <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" BGCOLOR="white">
          <TR>
            <TD BORDER="1" WIDTH="40">{dst_ports_content}</TD>
            <TD BGCOLOR="lightblue" ALIGN="CENTER"> <!-- Added ALIGN="CENTER" -->
              <B>{html.escape(node_tag_val)}</B>{manufacturer_line}{model_line}
            </TD>
            <TD BORDER="1" WIDTH="40">{src_ports_content}</TD>
          </TR>
        </TABLE>
        >'''
        
        # Node attributes: shape=plain is key for HTML-like labels to work as rectangles
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
            if cable_tag != "":
                label_parts.append(html.escape(cable_tag))
            if cable_type != "":
                label_parts.append(html.escape(cable_type))
            
            # Add src_port>dest_port to the label
            if src_port != "" and dst_port != "":
                label_parts.append(f"{html.escape(src_port)} > {html.escape(dst_port)}")

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


@app.get("/assets/search")
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

    processed_assets = clean_dataframe_for_json(filtered_assets)
    return processed_assets.to_dict(orient="records")


@app.get("/cables/filter")
async def filter_cables(
    target_tag: str,
    direction: str = "both",  # "in", "out", "both"
    cable_type: Optional[str] = None,
):
    """
    Filter cables based on a target asset tag, direction, and optional cable type.
    """
    if direction not in ["in", "out", "both"]:
        raise HTTPException(status_code=400, detail="Direction must be 'in', 'out', or 'both'.")

    filtered_cables = df_cables.copy()

    if direction == "in":
        filtered_cables = filtered_cables[filtered_cables["DstTag"] == target_tag]
    elif direction == "out":
        filtered_cables = filtered_cables[filtered_cables["SrcTag"] == target_tag]
    else:  # "both"
        filtered_cables = filtered_cables[
            (filtered_cables["DstTag"] == target_tag) | (filtered_cables["SrcTag"] == target_tag)
        ]

    if cable_type:
        filtered_cables = filtered_cables[
            filtered_cables["Type"].str.contains(cable_type, case=False, na=False)
        ]
            
    processed_cables = clean_dataframe_for_json(filtered_cables)
    return processed_cables.to_dict(orient="records")


@app.get("/graphviz/dot")
async def get_graphviz_dot(
    target_tag: str,
    direction: str = "both",
    cable_type: Optional[str] = None,
):
    """
    Generates a Graphviz DOT string for filtered cables.
    """
    # Use the existing cable filtering logic
    if direction not in ["in", "out", "both"]:
        raise HTTPException(status_code=400, detail="Direction must be 'in', 'out', or 'both'.")

    filtered_cables = df_cables.copy()

    if direction == "in":
        filtered_cables = filtered_cables[filtered_cables["DstTag"] == target_tag]
    elif direction == "out":
        filtered_cables = filtered_cables[filtered_cables["SrcTag"] == target_tag]
    else:  # "both"
        filtered_cables = filtered_cables[
            (filtered_cables["DstTag"] == target_tag) | (filtered_cables["SrcTag"] == target_tag)
        ]

    if cable_type:
        filtered_cables = filtered_cables[
            filtered_cables["Type"].str.contains(cable_type, case=False, na=False)
        ]
            
    # Include the target_tag itself even if it's not a src/dst in the filtered cables
    # (e.g., if it's an isolated node due to filtering)
    involved_tags = set(filtered_cables["SrcTag"].dropna().unique()).union(
        set(filtered_cables["DstTag"].dropna().unique())
    )
    if target_tag in df_assets["AssetTag"].values:
        involved_tags.add(target_tag)


    # Filter df_assets to only include assets that are part of the graph
    graph_assets = df_assets[df_assets["AssetTag"].isin(involved_tags)]
    
    dot_string = generate_dot_string(filtered_cables, graph_assets) # Renamed function
    
    # Try rendering the DOT string to SVG
    try:
        dot_source = graphviz.Source(dot_string) # Create a Graphviz Source object
        svg_output = dot_source.pipe(format='svg').decode('utf-8') # Render to SVG and decode
        return Response(content=svg_output, media_type="image/svg+xml") # Return as SVG
    except Exception as e:
        print(f"Error rendering Graphviz DOT to SVG: {e}")
        # If rendering fails, return the DOT string so the user can debug it
        raise HTTPException(status_code=500, detail=f"Error rendering Graphviz SVG: {e}")
