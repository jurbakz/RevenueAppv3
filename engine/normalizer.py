import pandas as pd
import numpy as np

def normalize_manifest_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Drop null clients
    if "client" in df.columns:
        df = df[~df["client"].isna()].copy()

    # Ensure all required columns exist with np.nan if missing (prevents KeyError)
    required_cols = [
        "client", "tracking_number", "status", "package_id", "delivery_type",
        "consignee_name", "consignee_full_address", "consignee_province",
        "consignee_city", "consignee_barangay", "shipper_address",
        "shipper_city", "shipper_province", "reference_2", "item_description",
        "total_price", "declared_value", "package_length", "package_width",
        "package_height", "package_weight"
    ]
    for col in required_cols:
        if col not in df.columns:
            # Check if return_* exists as alias for missing shipper_*
            if col.startswith("shipper_") and col.replace("shipper_", "return_") in df.columns:
                df[col] = df[col.replace("shipper_", "return_")]
            else:
                df[col] = np.nan

    # Fill numeric columns safely
    numeric_cols = ["total_price", "declared_value", "package_length", "package_width", "package_height", "package_weight"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    return df
