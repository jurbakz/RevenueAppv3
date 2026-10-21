import os
import sys
import time
import pandas as pd
import numpy as np

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from engine.cache import RateCache
from engine.pricing import process_manifest

CALCULATED_COLUMNS = [
    "cbm", "cwt", "final_destination", "final_origin", "segment",
    "transaction_type", "insurance_rate", "cod_rate", "cod", "valuation",
    "cbm_charge", "cwt_charge", "fuel_rate", "crating_rate", "ecom_rate",
    "vat", "total_amount"
]

def test_historical_parity():
    # 1. Load legacy ground truth file
    truth_file = os.path.abspath(os.path.join(project_root, "..", "RevenueAppv2", "export_data", "result_1772519845.csv"))
    assert os.path.exists(truth_file), f"Truth file not found: {truth_file}"
    truth_df = pd.read_csv(truth_file)
    row_count = len(truth_df)

    # 2. Extract raw inputs (the original upload before ecom_rate 1-to-many merge)
    raw_cols = [c for c in truth_df.columns if c not in CALCULATED_COLUMNS]
    raw_df = truth_df.drop_duplicates(subset=["tracking_number"])[raw_cols].copy()
    raw_row_count = len(raw_df)

    # 3. Load RateCache
    data_file = os.path.join(project_root, "data", "data.xlsx")
    t0_cache = time.time()
    cache = RateCache(data_file)
    cache_time = time.time() - t0_cache
    print(f"\n[CACHE] Loaded in {cache_time:.4f}s")

    # 4. Run v3 pipeline with timing
    t0_calc = time.time()
    result_df = process_manifest(raw_df, cache)
    calc_time = time.time() - t0_calc
    print(f"[CALC] Processed {raw_row_count} raw rows into {len(result_df)} evaluated rows in {calc_time*1000:.2f}ms ({calc_time:.4f}s)")

    # Latency assertion: must be < 500ms
    assert calc_time < 0.500, f"Calculation took too long: {calc_time:.4f}s (target < 0.5s)"

    # 5. Check row count and columns
    assert len(result_df) == row_count, f"Row count mismatch: {len(result_df)} vs {row_count}"
    for col in CALCULATED_COLUMNS:
        assert col in result_df.columns, f"Missing calculated column: {col}"

    # 6. Parity verification for each calculated column
    discrepancies = {}
    for col in CALCULATED_COLUMNS:
        expected = truth_df[col]
        actual = result_df[col]

        if np.issubdtype(expected.dtype, np.number):
            # Numeric comparison with small tolerance for floating point rounding
            diff = np.abs(expected.fillna(0).astype(float) - actual.fillna(0).astype(float))
            max_diff = diff.max()
            if max_diff > 0.05:  # Tolerance threshold (5 cents / floating diff)
                mismatch_idx = diff[diff > 0.05].index.tolist()
                discrepancies[col] = {
                    "max_diff": max_diff,
                    "mismatch_count": len(mismatch_idx),
                    "sample_expected": expected.iloc[mismatch_idx[:3]].tolist(),
                    "sample_actual": actual.iloc[mismatch_idx[:3]].tolist()
                }
        else:
            # String comparison (ignoring case and whitespace)
            exp_str = expected.fillna("").astype(str).str.strip().str.lower()
            act_str = actual.fillna("").astype(str).str.strip().str.lower()
            mismatches = exp_str != act_str
            if mismatches.any():
                mismatch_idx = mismatches[mismatches].index.tolist()
                discrepancies[col] = {
                    "mismatch_count": len(mismatch_idx),
                    "sample_expected": expected.iloc[mismatch_idx[:3]].tolist(),
                    "sample_actual": actual.iloc[mismatch_idx[:3]].tolist()
                }

    if discrepancies:
        print("\n[DISCREPANCIES FOUND]:")
        for col, err in discrepancies.items():
            print(f"  Column '{col}': {err}")

    assert not discrepancies, f"Found calculation discrepancies in columns: {list(discrepancies.keys())}"
    print("\n[SUCCESS] 100% PARITY CONFIRMED across all 17 columns!")

if __name__ == "__main__":
    test_historical_parity()
