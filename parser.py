from __future__ import annotations
import re
import os
from typing import Any, Dict, Tuple, Optional, List
import pandas as pd
from bs4 import BeautifulSoup

# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

UNIT_REGEX = re.compile(r"([-+]?\d*\.?\d+)")

def parse_numeric(value: str) -> Optional[float]:
    if value is None:
        return None
    m = UNIT_REGEX.search(str(value))
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None

def norm(s: str) -> str:
    return s.lower().replace(" ", "_")

# ------------------------------------------------------------
# Role inference
# ------------------------------------------------------------

def infer_role(name: str) -> str:
    n = norm(name)

    if any(k in n for k in ["speed", "velocity", "v_"]):
        return "speed"
    if any(k in n for k in ["overlap", "offset", "%"]):
        return "overlap"
    if any(k in n for k in ["impact"]):
        return "severity"
    if any(k in n for k in ["stop", "distance"]):
        return "distance"
    if any(k in n for k in ["t_", "time", "delay"]):
        return "timing"

    return "other"

# ------------------------------------------------------------
# Core parser
# ------------------------------------------------------------

def parse_report(html_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "lxml")

    rows: List[Dict[str, Any]] = []

    for h2 in soup.find_all("h2"):
        title = h2.get_text(strip=True)
        if not title.lower().startswith("scenario"):
            continue

        scenario_name = title.replace("Scenario :", "").strip()

        # ---------------- Stats ----------------
        stats = {}
        stats_tbl = h2.find_next("table", class_="stats")
        if stats_tbl:
            tds = [td.get_text(strip=True) for td in stats_tbl.find_all("td")]
            for i in range(0, len(tds), 2):
                stats[tds[i]] = tds[i + 1] if i + 1 < len(tds) else None

        # ---------------- Inputs ----------------
        inputs: Dict[str, Optional[float]] = {}
        roles: Dict[str, str] = {}

        params_tbl = h2.find_next("table", class_="parameters")
        if params_tbl:
            for tr in params_tbl.find_all("tr")[1:]:
                tds = tr.find_all("td")
                if len(tds) >= 3:
                    name = tds[0].get_text(strip=True)
                    val = parse_numeric(tds[2].get_text(strip=True))
                    inputs[name] = val
                    roles[name] = infer_role(name)

        # ---------------- Outputs ----------------
        outputs: Dict[str, Optional[float]] = {}

        out_tbl = h2.find_next("table", class_="outputs")
        if out_tbl:
            for tr in out_tbl.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) == 2:
                    name = tds[0].get_text(strip=True)
                    val = parse_numeric(tds[1].get_text(strip=True))
                    outputs[name] = val
                    roles[name] = infer_role(name)

        # ---------------- Criteria → Status ----------------
        status = "Unknown"
        crit_tbl = h2.find_next("table", class_="criteria")
        if crit_tbl:
            dot = crit_tbl.find("div", class_=re.compile(r"dot_"))
            if dot:
                cls = " ".join(dot.get("class", []))
                if "succeed" in cls:
                    status = "Pass"
                elif "failed" in cls:
                    status = "Fail"
                else:
                    status = "Error"

        # ---------------- Role resolution ----------------
        def pick(role):
            for k, r in roles.items():
                if r == role:
                    return inputs.get(k) or outputs.get(k)
            return None

        rec = {
            "scenario_name": scenario_name,
            "status": status,
            "state": status if status in ("Pass", "Fail") else "Error",
            "pass_flag": status == "Pass",

            # Dashboard‑expected canonical fields
            "ego_speed": pick("speed"),
            "overlap": pick("overlap"),
            "impact_speed": pick("severity"),
            "stop_distance": pick("distance"),
            "t_aeb": pick("timing"),

            # Metadata
            "date": stats.get("Date"),
            "real_duration": parse_numeric(stats.get("Real duration")),
            "real_time_ratio": parse_numeric(stats.get("Real time ratio")),
            "sim_duration": parse_numeric(stats.get("Simulated duration")),
        }

        # Preserve ALL raw fields
        for d in (inputs, outputs):
            for k, v in d.items():
                if k not in rec:
                    rec[k] = v

        rows.append(rec)

    df = pd.DataFrame(rows)

    # Ensure columns always exist
    for c in ["ego_speed", "overlap", "impact_speed", "stop_distance", "t_aeb"]:
        if c not in df.columns:
            df[c] = None

    # Coerce numerics
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="ignore")

    return df, {"mode": "auto-discovered"}