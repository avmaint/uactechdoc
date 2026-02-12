import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:9000",
    "file://", # Allow file:// origin for local development
    "null" # Some browsers (e.g., Chrome) use "null" for file:// origins
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def clean_dataframe_for_json(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans a DataFrame to make it JSON serializable by replacing NaN, NaT, and Inf
    with None, and converting datetimes to ISO format strings.
    """
    df_cleaned = df.copy()
    for col in df_cleaned.columns:
        print(f"DEBUG_CLEAN: Processing column '{col}' (initial dtype: {df_cleaned[col].dtype})")

        # Replace standard NaN, pd.NA, NaT and Inf with None
        df_cleaned[col] = df_cleaned[col].replace({
            np.nan: None,
            pd.NA: None,
            pd.NaT: None, # Explicitly handle NaT from datetime columns
            np.inf: None,
            -np.inf: None
        })
        
        # Handle datetime objects (which should now be None if NaT)
        if pd.api.types.is_datetime64_any_dtype(df_cleaned[col]):
            df_cleaned[col] = df_cleaned[col].apply(lambda x: x.isoformat() if x is not None else None)
        
        # Handle string 'nan' or 'none' that might be in object columns
        if pd.api.types.is_object_dtype(df_cleaned[col]):
            df_cleaned[col] = df_cleaned[col].apply(
                lambda x: None if isinstance(x, str) and (x.lower() == 'nan' or x.lower() == 'none') else x
            )
            
        # Final check for problematic float values
        problematic_values = [x for x in df_cleaned[col] if (isinstance(x, float) and (np.isinf(x) or np.isnan(x)))]
        if problematic_values:
            print(f"DEBUG_CLEAN: Column '{col}' STILL contains problematic float NaN/Inf values after aggressive cleaning: {problematic_values[:5]}")
        else:
            print(f"DEBUG_CLEAN: Column '{col}' appears definitively clean.")
            
    return df_cleaned

# --- Data Loading ---
def load_assets_data():
    """Loads asset data from uac_assets.xlsx."""
    try:
        df_assets = pd.read_excel("../data/uac_assets.xlsx", sheet_name="assets")
        # Filter out rows where AssetTag is NaN, as these seem to be summary/non-asset rows
        df_assets = df_assets.dropna(subset=["AssetTag"])
        return df_assets
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading asset data: {e}")

def load_cables_data():
    """Loads cable data from uac_cables.xlsx."""
    try:
        df_cables = pd.read_excel("../data/uac_cables.xlsx", sheet_name="Cables")
        return df_cables
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading cable data: {e}")

# Load data globally for the application to avoid reloading on each request
df_assets = load_assets_data()
df_cables = load_cables_data()


@app.get("/")
async def read_root():
    return {"message": "Welcome to the UAC Tech Documentation API"}

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

def generate_graphviz_dot(filtered_cables: pd.DataFrame, assets_df: pd.DataFrame) -> str:
    """
    Generates a Graphviz DOT string from filtered cable and asset data.
    """
    dot_nodes = set()
    dot_edges = []

    # Add nodes for source and destination tags
    for _, row in filtered_cables.iterrows():
        for tag_col in ["SrcTag", "DstTag"]:
            tag = row[tag_col]
            if pd.notna(tag) and tag != "":
                dot_nodes.add(tag)

    # Define nodes with additional information
    node_definitions = []
    for node_tag in sorted(list(dot_nodes)):
        asset_info = assets_df[assets_df["AssetTag"] == node_tag]
        label = node_tag
        if not asset_info.empty:
            manufacturer = asset_info["Manufacturer"].iloc[0]
            model = asset_info["Model"].iloc[0]
            usage = asset_info["Usage"].iloc[0] # Assuming 'Usage' is a column
            
            label_parts = [node_tag]
            if pd.notna(manufacturer) and manufacturer != "":
                label_parts.append(manufacturer)
            if pd.notna(model) and model != "":
                label_parts.append(model)
            # if pd.notna(usage) and usage != "":
            #     label_parts.append(f"({usage})") # Add usage if exists
            
            label = "\\n".join(label_parts)
            
        node_definitions.append(f'  "{node_tag}" [label="{label}"];')


    # Define edges
    for _, row in filtered_cables.iterrows():
        src_tag = row["SrcTag"]
        dst_tag = row["DstTag"]
        cable_tag = row["Tag"]
        cable_type = row["Type"]
        src_port = row["SrcPort"]
        dst_port = row["DstPort"]

        if pd.notna(src_tag) and pd.notna(dst_tag):
            label_parts = []
            if pd.notna(cable_tag) and cable_tag != "":
                label_parts.append(f"Cable: {cable_tag}")
            if pd.notna(cable_type) and cable_type != "":
                label_parts.append(f"Type: {cable_type}")
            if pd.notna(src_port) and src_port != "":
                label_parts.append(f"SrcPort: {src_port}")
            if pd.notna(dst_port) and dst_port != "":
                label_parts.append(f"DstPort: {dst_port}")
            
            edge_label = "\\n".join(label_parts) if label_parts else ""
            
            dot_edges.append(f'  "{src_tag}" -> "{dst_tag}" [label="{edge_label}"];')

    dot_string = "digraph G {\n  rankdir=LR;\n"
    dot_string += "\n".join(node_definitions)
    dot_string += "\n"
    dot_string += "\n".join(dot_edges)
    dot_string += "\n}"
    return dot_string

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
    
    return {"dot_string": generate_graphviz_dot(filtered_cables, graph_assets)}
