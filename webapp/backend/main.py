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
    Assumes DataFrame columns are already object dtype.
    """
    df_cleaned = df.copy()
    for col in df_cleaned.columns:
        cleaned_list = []
        for x in df_cleaned[col]:
            # Check for pandas/numpy NaN, None, NaT, Inf
            if pd.isna(x) or (isinstance(x, float) and (np.isinf(x) or np.isnan(x))):
                cleaned_list.append(None)
            # Handle explicit datetime objects
            elif isinstance(x, (pd.Timestamp, pd.Timedelta)):
                cleaned_list.append(x.isoformat())
            # Handle string 'nan' or 'none' in object columns
            elif isinstance(x, str) and (x.lower() == 'nan' or x.lower() == 'none'):
                cleaned_list.append(None)
            else:
                cleaned_list.append(x)
        df_cleaned[col] = cleaned_list
            
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
