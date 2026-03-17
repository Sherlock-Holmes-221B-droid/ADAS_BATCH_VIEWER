# parser.py
# ------------------------------------------------------------
# Robust, config-driven HTML parser for ADAS batch reports.
# - Accepts an optional JSON-like config (dict or path) to define:
#     * Which criteria row names to prefer (e.g., "impact_speed", "Pass_Fail")
#     * Aliases for the two label values shown on tiles (primary / secondary)
#     * Units for hover display
#     * How to treat execution-status failures (map to Error)
# - Returns: (pandas.DataFrame, merged_config)
#
# DataFrame columns (when available):
#   scenario_name, status, state, pass_flag,
#   ego_speed (primary), overlap (secondary),
#   label1_name, label2_name,
#   impact_speed, stop_distance, t_aeb, aeb_activation, result_code,
#   date, real_duration, real_time_ratio, sim_duration
#
# Compatible with HtmltoReport.py provided earlier.
# ------------------------------------------------------------

from __future__ import annotations

import os
import re
import json
from typing import Any, Dict, Tuple, Optional, List

import pandas as pd
from bs4 import BeautifulSoup


# -------------------- DEFAULT CONFIG --------------------
DEFAULT_CONFIG: Dict[str, Any] = {
    "criteria": {
        # We will try these row names (in order) inside the "Scenario criteria" table.
        # If none is found, we'll fall back to "first dot_* anywhere in the table".
        "row_names": ["impact_speed", "Pass_Fail"],
        "prefer_first_dot_if_missing": True,
        # Map HTML dot classes to status strings expected by the UI
        "map_dot_to_status": {
            "dot_succeed": "Pass",
            "dot_failed": "Fail",
            "dot_mixed": "Mixed",
            "dot_unkown": "Unknown",  # some reports misspell "unknown"
            "dot_unknown": "Unknown"
        },
        # If Execution Status says "failed", classify as Error (unless we already have Fail)
        "use_execution_status_for_error": True
    },
    "labels": {
        # The two label values we show on each tile.
        # Provide alias lists for different report families (AEB/ELK/etc.)
        "primary": {
            "aliases": [
                "Param_Test_Ego_Speed",
                "Param_Test_Velocity",
                "Param_V_Ego",
                "Param_Test_V",
                "Param_Test_V_Lat"  # ELK-style
            ],
            "unit": " km/h"  # used in hover by the app
        },
        "secondary": {
            "aliases": [
                "Param_Test_Overlap",
                "Param_Overlap",
                "Param_Test_OL",
                "Param_TTLC",       # ELK-style fallback
                "Param_DTLE"
            ],
            "unit": " %"
        }
    }
}


# -------------------- UTILITIES --------------------
def _to_float(x: Any) -> Optional[float]:
    """Convert a cell text to float if possible; else None."""
    try:
        s = str(x).strip().replace(",", "")
        if s == "" or s.lower() in ("nan", "none"):
            return None
        return float(s)
    except Exception:
        return None


def _merge(a: Any, b: Any) -> Any:
    """Deep-merge dict b into dict a (immutably)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = _merge(a.get(k), v)
        return out
    return b if b is not None else a


def load_config(path_or_dict: Optional[Any]) -> Dict[str, Any]:
    """Load and merge user config with DEFAULT_CONFIG."""
    if path_or_dict is None:
        return DEFAULT_CONFIG
    if isinstance(path_or_dict, dict):
        return _merge(DEFAULT_CONFIG, path_or_dict)
    if isinstance(path_or_dict, str) and os.path.exists(path_or_dict):
        try:
            with open(path_or_dict, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            return _merge(DEFAULT_CONFIG, data)
        except Exception:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG


def _pick_from_aliases(params: Dict[str, Optional[float]], aliases: List[str]) -> Tuple[Optional[float], Optional[str]]:
    """Pick the first available parameter from alias list."""
    for key in aliases:
        if key in params and params[key] is not None:
            return params[key], key
    return None, None


def _derive_state(status: str) -> str:
    """Map status to tri-state used in UI: Pass / Fail / Error."""
    return status if status in ("Pass", "Fail") else "Error"


# -------------------- CORE PARSER --------------------
def parse_report(html_path: str, config: Optional[Any] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Parse the batch HTML and return (DataFrame, merged_config).

    Parameters
    ----------
    html_path : str
        Path to the batch HTML file
    config : dict | str | None
        - None  -> use DEFAULT_CONFIG
        - dict  -> merge with DEFAULT_CONFIG
        - str   -> path to a JSON config file (merged with DEFAULT_CONFIG)
    """
    cfg = load_config(config)

    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "lxml")

    rows: List[Dict[str, Any]] = []

    # We identify scenarios by <h2> whose text begins with "Scenario".
    for h2 in soup.find_all("h2"):
        title = h2.get_text(strip=True)
        if not title.lower().startswith("scenario"):
            continue

        # Scenario name is everything after "Scenario :"
        scenario_name = title.replace("Scenario :", "").strip()

        # ---- Simulation Infos (execution status, durations, etc.)
        real_duration = real_time_ratio = sim_duration = None
        exec_status = None
        date_str = None

        stats_tbl = h2.find_next("table", {"class": "stats"})
        if stats_tbl:
            td_texts = [td.get_text(strip=True) for td in stats_tbl.find_all("td")]
            for i in range(0, len(td_texts), 2):
                key = td_texts[i]
                val = td_texts[i + 1] if i + 1 < len(td_texts) else ""
                if key == "Execution Status":
                    # e.g., "Executed" or "Execution failed"
                    exec_status = val
                elif key == "Date":
                    date_str = val
                elif key == "Real duration":
                    real_duration = _to_float(val)
                elif key == "Real time ratio":
                    real_time_ratio = _to_float(val)
                elif key == "Simulated duration":
                    sim_duration = _to_float(val)

        # Sanitize negative placeholders often seen in some reports
        if isinstance(real_time_ratio, float) and real_time_ratio < 0:
            real_time_ratio = None
        if isinstance(sim_duration, float) and sim_duration < 0:
            sim_duration = None

        # ---- Input Parameters (Name / Type / Value / Description)
        params: Dict[str, Optional[float]] = {}
        params_tbl = h2.find_next("table", {"class": "parameters"})
        if params_tbl:
            # Expect header row first; next rows are data
            for tr in params_tbl.find_all("tr")[1:]:
                cells = tr.find_all(["td", "th"])
                # Some exports use <th> in the header and 3 or 4 cells in rows
                if len(cells) >= 3:
                    name = cells[0].get_text(strip=True)
                    val  = _to_float(cells[2].get_text(strip=True))
                    params[name] = val

        # Resolve primary/secondary label values via aliases (config)
        p_val, p_key = _pick_from_aliases(params, cfg["labels"]["primary"]["aliases"])
        s_val, s_key = _pick_from_aliases(params, cfg["labels"]["secondary"]["aliases"])

        # ---- Outputs (optional; two-column table)
        outs: Dict[str, Optional[float]] = {}
        outs_tbl = h2.find_next("table", {"class": "outputs"})
        if outs_tbl:
            for tr in outs_tbl.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) == 2:
                    k = tds[0].get_text(strip=True)
                    v = _to_float(tds[1].get_text(strip=True))
                    outs[k] = v

        # ---- Criteria (status via colored dot)
        status = "Unknown"
        crit_tbl = h2.find_next("table", {"class": "criteria"})
        if crit_tbl:
            found = False
            # 1) Prefer specific row names when present
            # (e.g., "impact_speed" or "Pass_Fail" depending on report family)
            row_names = [s.lower() for s in cfg["criteria"].get("row_names", [])]
            for tr in crit_tbl.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) == 2:
                    name = tds[0].get_text(strip=True).lower()
                    if name in row_names:
                        dot = tds[1].find("div", class_=re.compile(r"^dot_"))
                        if dot:
                            for cls in dot.get("class", []):
                                mapped = cfg["criteria"]["map_dot_to_status"].get(cls)
                                if mapped:
                                    status = mapped
                                    found = True
                                    break
                if found:
                    break

            # 2) Fallback: first dot_* anywhere in the criteria table
            if not found and cfg["criteria"].get("prefer_first_dot_if_missing", True):
                dot = crit_tbl.find("div", class_=re.compile(r"^dot_"))
                if dot:
                    for cls in dot.get("class", []):
                        mapped = cfg["criteria"]["map_dot_to_status"].get(cls)
                        if mapped:
                            status = mapped
                            break

        # ---- Execution-status -> Error mapping (if configured)
        if cfg["criteria"].get("use_execution_status_for_error", True) and exec_status:
            # Many non-AEB exports mark runs as "Execution failed"
            if "fail" in exec_status.lower() and status != "Fail":
                status = "Error"

        # Build the scenario record
        rec: Dict[str, Any] = {
            "scenario_name": scenario_name,
            "status": status,
            "state": _derive_state(status),
            "pass_flag": (status == "Pass"),

            # Primary/secondary used by the tiles (HtmltoReport expects these names)
            "ego_speed": p_val,
            "overlap": s_val,
            "label1_name": p_key,
            "label2_name": s_key,

            # Common AEB outputs (may be None in non-AEB reports)
            "impact_speed": outs.get("Out_Speed_Impact") if outs else None,
            "stop_distance": outs.get("Out_Stop_Distance") if outs else None,
            "t_aeb": outs.get("Out_T_AEB") if outs else None,
            "aeb_activation": outs.get("Out_Scenario_AEB_Activation") if outs else None,
            "result_code": outs.get("Out_Scenario_Result") if outs else None,

            # Metadata
            "date": date_str,
            "real_duration": real_duration,
            "real_time_ratio": real_time_ratio,
            "sim_duration": sim_duration,
        }

        # (Optional) also expose generic names some callers may look for
        # rec["primary_value"] = rec["ego_speed"]
        # rec["secondary_value"] = rec["overlap"]

        for k, v in params.items():
            # Avoid overwriting fields we already set (like ego_speed/overlap)
            if k not in rec:
                rec[k] = v

        rows.append(rec)


    df = pd.DataFrame(rows)

    # Ensure expected columns exist even if empty
    for col in [
        "scenario_name", "status", "state", "pass_flag",
        "ego_speed", "overlap", "label1_name", "label2_name",
        "impact_speed", "stop_distance", "t_aeb", "aeb_activation", "result_code",
        "date", "real_duration", "real_time_ratio","Param_Test_V_Lat", "sim_duration",
        "primary_value", "secondary_value"
    ]:
        if col not in df.columns:
            df[col] = None

    # Types (best-effort)
    for num_col in ["ego_speed", "overlap", "impact_speed", "stop_distance", "t_aeb",
                    "aeb_activation", "result_code", "real_duration",
                    "real_time_ratio", "sim_duration","Param_Test_V_Lat", "primary_value", "secondary_value"]:
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

    df["pass_flag"] = df["pass_flag"].fillna(False).astype(bool)
    df["status"] = df["status"].fillna("Unknown").astype(str)
    df["state"]  = df["state"].fillna("Error").astype(str)
    df["scenario_name"] = df["scenario_name"].fillna("").astype(str)

    return df, cfg