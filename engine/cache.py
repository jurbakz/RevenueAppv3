import os
import pickle
import pandas as pd
import numpy as np

class RateCache:
    def __init__(self, data_file):
        self.data_file = data_file
        self.cbm_rules = {}
        self.segment_rules = {}
        self.transaction_type_rules = {}
        self.origin_rules = {}
        self.destination_rules = {}
        self.other_charges_rules = {}
        self.cbm_rates = {}
        self.cwt_rates = {}
        self.ecom_rate_df = None
        self._load()

    def _cache_path(self):
        base, _ = os.path.splitext(self.data_file)
        return f"{base}_cache.pkl"

    def _load(self):
        if not os.path.exists(self.data_file):
            raise FileNotFoundError(f"Rate file not found: {self.data_file}")

        cache_file = self._cache_path()
        if os.path.exists(cache_file):
            try:
                if os.path.getmtime(cache_file) >= os.path.getmtime(self.data_file):
                    with open(cache_file, "rb") as f:
                        cached_dict = pickle.load(f)
                    self.__dict__.update(cached_dict)
                    return
            except Exception as e:
                print(f"[RateCache] Cache load failed, regenerating: {e}")

        self._load_from_excel()

        try:
            with open(cache_file, "wb") as f:
                pickle.dump(self.__dict__, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            print(f"[RateCache] Failed to save pickle cache: {e}")

    def _load_from_excel(self):
        sheets = pd.read_excel(self.data_file, sheet_name=None)

        # 1. cbm_computation rules
        cbm_comp = sheets.get("cbm_computation")
        if cbm_comp is not None:
            for _, r in cbm_comp.iterrows():
                client = str(r["client"]).strip() if pd.notna(r["client"]) else ""
                prov = str(r["consignee_province"]).strip() if pd.notna(r["consignee_province"]) else "*"
                self.cbm_rules[(client, prov)] = {
                    "cbm_formula": r["cbm_formula"] if pd.notna(r["cbm_formula"]) else None,
                    "cwt_formula": r["cwt_formula"] if pd.notna(r["cwt_formula"]) else None,
                    "min_cbm": float(r["min_cbm"]) if pd.notna(r["min_cbm"]) else 0.0
                }

        # 2. segment rules
        segment_df = sheets.get("segment")
        if segment_df is not None:
            for _, r in segment_df.iterrows():
                client = str(r["client"]).strip() if pd.notna(r["client"]) else ""
                if client not in self.segment_rules:
                    self.segment_rules[client] = []
                self.segment_rules[client].append({
                    "package_id": str(r["package_id"]).strip() if pd.notna(r["package_id"]) else "*",
                    "delivery_type": str(r["delivery_type"]).strip() if pd.notna(r["delivery_type"]) else "*",
                    "formula": str(r["formula"]).strip() if pd.notna(r["formula"]) else "*",
                    "segment": r["segment"] if pd.notna(r["segment"]) else np.nan
                })

        # 3. transaction_type rules
        tt_df = sheets.get("transaction_type")
        if tt_df is not None:
            for _, r in tt_df.iterrows():
                client = str(r["client"]).strip() if pd.notna(r["client"]) else ""
                if client not in self.transaction_type_rules:
                    self.transaction_type_rules[client] = []
                self.transaction_type_rules[client].append({
                    "tracking_number": str(r["tracking_number"]).strip() if pd.notna(r["tracking_number"]) else "*",
                    "reference_2": str(r["reference_2"]).strip().lower() if pd.notna(r["reference_2"]) else "*",
                    "item_description": str(r["item_description"]).strip().lower() if pd.notna(r["item_description"]) else "*",
                    "transaction_type": r["transaction_type"] if pd.notna(r["transaction_type"]) else "trad"
                })

        # 4. address_mapping rules (origin & destination)
        addr_df = sheets.get("address_mapping")
        if addr_df is not None:
            for _, r in addr_df.iterrows():
                client = str(r["client"]).strip() if pd.notna(r["client"]) else ""
                if client not in self.origin_rules:
                    self.origin_rules[client] = []
                if client not in self.destination_rules:
                    self.destination_rules[client] = []

                self.origin_rules[client].append({
                    "shipper_city": str(r["shipper_city"]).strip().lower() if pd.notna(r.get("shipper_city")) else "*",
                    "shipper_province": str(r["shipper_province"]).strip().lower() if pd.notna(r.get("shipper_province")) else "*",
                    "final_origin": r["final_origin"] if pd.notna(r.get("final_origin")) else "UNKNOWN"
                })
                self.destination_rules[client].append({
                    "consignee_province": str(r["consignee_province"]).strip().lower() if pd.notna(r.get("consignee_province")) else "*",
                    "final_destination": r["final_destination"] if pd.notna(r.get("final_destination")) else "UNKNOWN"
                })

        # 5. other_charges rules
        other_df = sheets.get("other_charges")
        if other_df is not None:
            for _, r in other_df.iterrows():
                client = str(r["client"]).strip() if pd.notna(r["client"]) else ""
                if client not in self.other_charges_rules:
                    self.other_charges_rules[client] = []
                self.other_charges_rules[client].append({
                    "status": str(r["status"]).strip().lower() if pd.notna(r.get("status")) else "*",
                    "consignee_province": str(r["consignee_province"]).strip().lower() if pd.notna(r.get("consignee_province")) else "*",
                    "consignee_city": str(r["consignee_city"]).strip().lower() if pd.notna(r.get("consignee_city")) else "*",
                    "segment": str(r["segment"]).strip().lower() if pd.notna(r.get("segment")) else "*",
                    "is_active": str(r["is_active"]).strip().lower() if pd.notna(r.get("is_active")) else "",
                    "insurance_rate": float(r["insurance_rate"]) if pd.notna(r.get("insurance_rate")) else 0.0,
                    "cod": float(r["cod"]) if pd.notna(r.get("cod")) else 0.0,
                    "fuel": float(r["fuel"]) if pd.notna(r.get("fuel")) else 0.0,
                    "crating": float(r["crating"]) if pd.notna(r.get("crating")) else 0.0
                })

        # 6. rate_per_cbm rules
        cbm_rate_df = sheets.get("rate_per_cbm")
        if cbm_rate_df is not None:
            for _, r in cbm_rate_df.iterrows():
                client = str(r["client"]).strip() if pd.notna(r["client"]) else ""
                if client not in self.cbm_rates:
                    self.cbm_rates[client] = []
                self.cbm_rates[client].append({
                    "segment": str(r["segment"]).strip().lower() if pd.notna(r.get("segment")) else "*",
                    "shipper_address": str(r["shipper_address"]).strip().lower() if pd.notna(r.get("shipper_address")) else "*",
                    "consignee_name": str(r["consignee_name"]).strip().lower() if pd.notna(r.get("consignee_name")) else "*",
                    "consignee_full_address": str(r["consignee_full_address"]).strip().lower() if pd.notna(r.get("consignee_full_address")) else "*",
                    "consignee_province": str(r["consignee_province"]).strip().lower() if pd.notna(r.get("consignee_province")) else "*",
                    "consignee_city": str(r["consignee_city"]).strip().lower() if pd.notna(r.get("consignee_city")) else "*",
                    "consignee_barangay": str(r["consignee_barangay"]).strip().lower() if pd.notna(r.get("consignee_barangay")) else "*",
                    "rate_0_5": float(r["rate_0_5"]) if pd.notna(r.get("rate_0_5")) else 0.0,
                    "rate_1": float(r["rate_1"]) if pd.notna(r.get("rate_1")) else 0.0
                })

        # 7. rate_per_cwt rules
        cwt_rate_df = sheets.get("rate_per_cwt")
        if cwt_rate_df is not None:
            for _, r in cwt_rate_df.iterrows():
                client = str(r["client"]).strip() if pd.notna(r["client"]) else ""
                if client not in self.cwt_rates:
                    self.cwt_rates[client] = []
                self.cwt_rates[client].append({
                    "segment": str(r["segment"]).strip().lower() if pd.notna(r.get("segment")) else "*",
                    "transaction_type": str(r["transaction_type"]).strip().lower() if pd.notna(r.get("transaction_type")) else "*",
                    "shipper_address": str(r["shipper_address"]).strip().lower() if pd.notna(r.get("shipper_address")) else "*",
                    "consignee_name": str(r["consignee_name"]).strip().lower() if pd.notna(r.get("consignee_name")) else "*",
                    "consignee_full_address": str(r["consignee_full_address"]).strip().lower() if pd.notna(r.get("consignee_full_address")) else "*",
                    "consignee_province": str(r["consignee_province"]).strip().lower() if pd.notna(r.get("consignee_province")) else "*",
                    "consignee_city": str(r["consignee_city"]).strip().lower() if pd.notna(r.get("consignee_city")) else "*",
                    "Rate": float(r["Rate"]) if pd.notna(r.get("Rate")) else 0.0,
                    "minmum_kg": float(r["minmum_kg"]) if pd.notna(r.get("minmum_kg")) else 0.0,
                    "exceeding_per_kg": float(r["exceeding_per_kg"]) if pd.notna(r.get("exceeding_per_kg")) else 0.0
                })

        # 8. ecom_rate df
        ecom_df = sheets.get("ecom_rate")
        if ecom_df is not None:
            self.ecom_rate_df = ecom_df[["client", "final_origin", "final_destination", "transaction_type", "cwt", "ecom_rate"]].copy()
