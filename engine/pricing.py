import math
import numpy as np
import pandas as pd
from engine.normalizer import normalize_manifest_df
from engine.cache import RateCache

def str_match(rule_val, row_val) -> bool:
    """Matches rules against row values using legacy substring matching rules."""
    if rule_val == "*":
        return True
    r = str(rule_val).lower().strip()
    t = str(row_val).lower().strip()
    return (r in t) or (t in r)

def process_manifest(input_df: pd.DataFrame, cache: RateCache) -> pd.DataFrame:
    df = normalize_manifest_df(input_df)
    records = df.to_dict("records")
    n = len(records)

    cbm_list = [np.nan] * n
    cwt_list = [np.nan] * n
    dest_list = ["UNKNOWN"] * n
    orig_list = ["UNKNOWN"] * n
    segment_list = [np.nan] * n
    trans_type_list = ["trad"] * n
    ins_rate_list = [0.0] * n
    cod_rate_list = [0.0] * n
    cbm_charge_list = [0.0] * n
    cwt_charge_list = [0.0] * n
    fuel_list = [0.0] * n
    crating_list = [0.0] * n

    for i, r in enumerate(records):
        client = str(r["client"]).strip() if pd.notna(r["client"]) else ""
        c_prov = r["consignee_province"]
        c_city = r["consignee_city"]
        c_brgy = r["consignee_barangay"]
        c_name = r["consignee_name"]
        c_addr = r["consignee_full_address"]
        s_city = r["shipper_city"]
        s_prov = r["shipper_province"]
        s_addr = r["shipper_address"]
        status = r["status"]
        pkg_id = r["package_id"]
        del_type = r["delivery_type"]
        track_no = r["tracking_number"]
        ref_2 = r["reference_2"]
        item_desc = r["item_description"]

        L = r["package_length"]
        W = r["package_width"]
        H = r["package_height"]
        act = r["package_weight"]

        # 1. CBM and CWT
        prov_key = str(c_prov).strip() if pd.notna(c_prov) else "*"
        cbm_rule = cache.cbm_rules.get((client, prov_key)) or cache.cbm_rules.get((client, "*"))
        row_cbm = np.nan
        row_cwt = np.nan
        if cbm_rule:
            if cbm_rule["cbm_formula"]:
                try:
                    cbm_val = eval(str(cbm_rule["cbm_formula"]))
                    row_cbm = max(cbm_rule["min_cbm"], round(cbm_val, 2))
                except Exception:
                    pass
            if cbm_rule["cwt_formula"]:
                try:
                    row_cwt = eval(str(cbm_rule["cwt_formula"]))
                except Exception:
                    pass
        cbm_list[i] = row_cbm
        cwt_list[i] = row_cwt

        # 2. Final Destination
        final_dest = "UNKNOWN"
        for rule in cache.destination_rules.get(client, []):
            if str_match(rule["consignee_province"], c_prov):
                final_dest = rule["final_destination"]
                break
        dest_list[i] = final_dest

        # 3. Final Origin (1st pass city, 2nd pass province)
        final_orig = "UNKNOWN"
        orig_rules = cache.origin_rules.get(client, [])
        for rule in orig_rules:
            if str_match(rule["shipper_city"], s_city):
                final_orig = rule["final_origin"]
                break
        if final_orig == "UNKNOWN":
            for rule in orig_rules:
                if str_match(rule["shipper_province"], s_prov):
                    final_orig = rule["final_origin"]
                    break
        orig_list[i] = final_orig

        # 4. Segment
        row_segment = np.nan
        for srule in cache.segment_rules.get(client, []):
            if srule["package_id"] != "*":
                if str_match(srule["package_id"], pkg_id):
                    row_segment = srule["segment"]
                    break
            if srule["delivery_type"] != "*":
                if str_match(srule["delivery_type"], del_type):
                    row_segment = srule["segment"]
                    break
            if srule["formula"] != "*":
                try:
                    ctx = {
                        "L": L, "W": W, "H": H, "act": act,
                        "package_length": L, "package_width": W,
                        "package_height": H, "package_weight": act
                    }
                    res = eval(srule["formula"], {}, ctx)
                    if isinstance(res, (bool, np.bool_)) and res:
                        row_segment = srule["segment"]
                        break
                except Exception:
                    continue
            if srule["package_id"] == "*" and srule["formula"] == "*" and srule["delivery_type"] == "*":
                row_segment = srule["segment"]
                break
        segment_list[i] = row_segment

        # 5. Transaction Type
        row_tt = "trad"
        for trule in cache.transaction_type_rules.get(client, []):
            tn_rule = trule["tracking_number"]
            tn_match = (tn_rule == "*") or str(track_no).startswith(tn_rule.replace("*", ""))
            ref_match = (trule["reference_2"] == "*") or (trule["reference_2"] in str(ref_2).lower())
            item_match = (trule["item_description"] == "*") or (trule["item_description"] in str(item_desc).lower())
            if tn_match and ref_match and item_match:
                row_tt = trule["transaction_type"]
                break
        trans_type_list[i] = row_tt

        # 6. Other Charges: Insurance, COD, Fuel, Crating
        row_ins = 0.0
        row_cod = 0.0
        row_fuel = 0.0
        row_crating = 0.0
        seg_str = str(row_segment) if pd.notna(row_segment) else ""

        for oc in cache.other_charges_rules.get(client, []):
            status_match = str_match(oc["status"], status)
            prov_match = str_match(oc["consignee_province"], c_prov)
            city_match = str_match(oc["consignee_city"], c_city)
            seg_match = str_match(oc["segment"], seg_str)

            # Insurance
            if row_ins == 0.0 and prov_match and city_match and status_match:
                row_ins = oc["insurance_rate"]

            # COD
            if row_cod == 0.0 and prov_match and city_match and status_match and (oc["is_active"] == "yes"):
                row_cod = oc["cod"]

            # Fuel (Province wins first, else City, or Segment)
            if row_fuel == 0.0:
                if seg_match or prov_match or city_match:
                    row_fuel = oc["fuel"]

            # Crating
            if row_crating == 0.0:
                if seg_match or prov_match or city_match:
                    row_crating = oc["crating"]

        ins_rate_list[i] = row_ins
        cod_rate_list[i] = row_cod
        fuel_list[i] = row_fuel
        crating_list[i] = row_crating

        # 7. CBM Rate Charge
        row_cbm_charge = 0.0
        if pd.notna(row_cbm) and row_cbm > 0:
            for cb in cache.cbm_rates.get(client, []):
                if (str_match(cb["segment"], seg_str) and
                    str_match(cb["shipper_address"], s_addr) and
                    str_match(cb["consignee_name"], c_name) and
                    str_match(cb["consignee_full_address"], c_addr) and
                    str_match(cb["consignee_province"], c_prov) and
                    str_match(cb["consignee_city"], c_city) and
                    str_match(cb["consignee_barangay"], c_brgy)):

                    has_half = cb["rate_0_5"] > 0
                    if row_cbm >= 1:
                        row_cbm_charge = row_cbm * cb["rate_1"]
                    elif row_cbm < 1 and has_half:
                        if row_cbm <= 0.5:
                            row_cbm_charge = cb["rate_0_5"]
                        else:
                            row_cbm_charge = cb["rate_0_5"] + ((row_cbm - 0.5) * cb["rate_0_5"])
                    else:
                        row_cbm_charge = row_cbm * cb["rate_1"]
                    break
        cbm_charge_list[i] = row_cbm_charge

        # 8. CWT Rate Charge
        row_cwt_charge = 0.0
        if pd.notna(row_cwt) and row_cwt > 0:
            for cw in cache.cwt_rates.get(client, []):
                if (str_match(cw["segment"], seg_str) and
                    str_match(cw["transaction_type"], row_tt) and
                    str_match(cw["shipper_address"], s_addr) and
                    str_match(cw["consignee_name"], c_name) and
                    str_match(cw["consignee_full_address"], c_addr) and
                    str_match(cw["consignee_province"], c_prov) and
                    str_match(cw["consignee_city"], c_city)):

                    base = cw["Rate"]
                    min_kg = cw["minmum_kg"]
                    exceed = cw["exceeding_per_kg"]
                    row_cwt_charge = base + max(0.0, (row_cwt - min_kg)) * exceed
                    break
        cwt_charge_list[i] = row_cwt_charge

    # Assign calculated arrays
    df["cbm"] = cbm_list
    df["cwt"] = cwt_list
    df["final_destination"] = dest_list
    df["final_origin"] = orig_list
    df["segment"] = segment_list
    df["transaction_type"] = trans_type_list
    df["insurance_rate"] = ins_rate_list
    df["cod_rate"] = cod_rate_list
    df["cbm_charge"] = cbm_charge_list
    df["cwt_charge"] = cwt_charge_list
    df["fuel_rate"] = fuel_list
    df["crating_rate"] = crating_list

    # Vectorized computations
    df["cod"] = df["cod_rate"] * df["total_price"]
    df["valuation"] = df["declared_value"] * df["insurance_rate"]

    # Ecom rate attach
    if "ecom_rate" in df.columns:
        df = df.drop(columns=["ecom_rate"])

    if cache.ecom_rate_df is not None:
        rates = cache.ecom_rate_df[["client", "final_origin", "final_destination", "transaction_type", "cwt", "ecom_rate"]]
        df = df.merge(
            rates,
            how="left",
            on=["client", "final_origin", "final_destination", "transaction_type", "cwt"]
        )
        df["ecom_rate"] = df["ecom_rate"].fillna(0.0)
    else:
        df["ecom_rate"] = 0.0

    # Tax & Total
    df["vat"] = (
        df["cod"] +
        df["cbm_charge"] +
        df["cwt_charge"] +
        df["fuel_rate"] +
        df["crating_rate"] +
        df["valuation"] +
        df["ecom_rate"]
    ) * 0.12

    df["total_amount"] = (
        df["cod"] +
        df["cbm_charge"] +
        df["cwt_charge"] +
        df["fuel_rate"] +
        df["crating_rate"] +
        df["valuation"] +
        df["vat"] +
        df["ecom_rate"]
    )

    return df
