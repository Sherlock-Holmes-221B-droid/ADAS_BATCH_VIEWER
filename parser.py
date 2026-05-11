from __future__ import annotations

import re
from typing import Any, Dict, Tuple, Optional, List
import pandas as pd
from bs4 import BeautifulSoup

# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

_NUM_RE = re.compile(r"([-+]?\d*\.?\d+)")

def _extract_dot_status(tag) -> str:
    """
    Extract status from dot_* class in HTML
    """
    if tag is None:
        return "Error"

    dot = tag.find("div", class_=True)
    if dot is None:
        return "Error"

    classes = " ".join(dot.get("class", []))

    if "dot_succeed" in classes:
        return "Pass"
    elif "dot_failed" in classes:
        return "Fail"
    elif "dot_mixed" in classes:
        return "Mixed"
    else:
        return "Error"



def parse_numeric(val: Any) -> Optional[float]:
    """Extract first numeric value from a cell (handles units)."""
    if val is None:
        return None
    m = _NUM_RE.search(str(val))
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def normalize(name: str) -> str:
    return name.lower().replace(" ", "_")


# ------------------------------------------------------------
# Semantic role inference (NOT canonical columns)
# ------------------------------------------------------------

def infer_role(name: str) -> str:
    n = normalize(name)

    if any(k in n for k in ["speed", "velocity", "v_"]):
        return "speed"
    if any(k in n for k in ["overlap", "offset", "%"]):
        return "overlap"
    if "impact" in n:
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

        # ---------------- Simulation Infos ----------------
        stats: Dict[str, Optional[str]] = {}
        exec_status = None

        stats_tbl = h2.find_next("table", class_="stats")
        if stats_tbl:
            cells = [td.get_text(strip=True) for td in stats_tbl.find_all("td")]
            for i in range(0, len(cells), 2):
                key = cells[i]
                val = cells[i + 1] if i + 1 < len(cells) else None
                stats[key] = val
                if key == "Execution Status":
                    exec_status = val

        # ---------------- Input Parameters ----------------
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

        def pick_input(role: str) -> Optional[float]:
            for k, v in inputs.items():
                if roles.get(k) == role and v is not None:
                    return v
            return None

        ego_speed = pick_input("speed")
        overlap = pick_input("overlap")

        # ---------------- Output Parameters ----------------
        outs: Dict[str, Optional[float]] = {}
        outs_tbl = h2.find_next("table", class_="outputs")
        if outs_tbl:
            for tr in outs_tbl.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) == 2:
                    k = tds[0].get_text(strip=True)
                    v = parse_numeric(tds[1].get_text(strip=True))
                    outs[k] = v
                    roles[k] = infer_role(k)

        # --------------------------------------------------
        # ✅ AUTHORITATIVE OUTPUTS (same as old parser)
        # --------------------------------------------------

        impact_speed = None
        stop_distance = None
        t_aeb = None
        aeb_activation = None
        result_code = None

        if outs:
            impact_speed = outs.get("Out_Speed_Impact")
            stop_distance = outs.get("Out_Stop_Distance")
            t_aeb = outs.get("Out_T_AEB")
            aeb_activation = outs.get("Out_Scenario_AEB_Activation")
            result_code = outs.get("Out_Scenario_Result")

        # --------------------------------------------------
        # 🔁 Fallback for new HTML formats (inference-based)
        # --------------------------------------------------

        if impact_speed is None:
            impact_speed = next(
                (v for k, v in outs.items()
                 if "impact_speed" in normalize(k) and v is not None),
                None
            )

        if stop_distance is None:
            stop_distance = next(
                (v for k, v in outs.items()
                 if "stop_distance" in normalize(k) and v is not None),
                None
            )

        if t_aeb is None:
            t_aeb = next(
                (v for k, v in outs.items()
                 if normalize(k) == "t_aeb" and v is not None),
                None
            )

        # ---------------- Criteria → Status ----------------
        status = "Unknown"
        #status = _extract_dot_status(li_tag)

        crit_tbl = h2.find_next("table", class_="criteria")
        if crit_tbl:
            dot = crit_tbl.find("div", class_=re.compile(r"^dot_"))
            if dot:
                cls = " ".join(dot.get("class", []))
                if "succeed" in cls:
                    status = "Pass"
                elif "failed" in cls:
                    status = "Fail"
                elif "dot_mixed" in cls:
                    status = "Mixed"
                else:
                    status = "Error"

        if exec_status and "fail" in exec_status.lower() and status != "Fail":
            status = "Error"

        state = status if status in ("Pass", "Fail", "Mixed") else "Error"

        # ---------------- Record ----------------
        rec: Dict[str, Any] = {
            "scenario_name": scenario_name,
            "status": status,
            "state": state,
            "pass_flag": (status == "Pass"),

            "ego_speed": ego_speed,
            "overlap": overlap,

            "impact_speed": impact_speed,
            "stop_distance": stop_distance,
            "t_aeb": t_aeb,
            "aeb_activation": aeb_activation,
            "result_code": result_code,

            "date": stats.get("Date"),
            "real_duration": parse_numeric(stats.get("Real duration")),
            "real_time_ratio": parse_numeric(stats.get("Real time ratio")),
            "sim_duration": parse_numeric(stats.get("Simulated duration")),
        }

        # Preserve all raw fields
        for d in (inputs, outs):
            for k, v in d.items():
                if k not in rec:
                    rec[k] = v

        rows.append(rec)

    df = pd.DataFrame(rows)

    # Ensure dashboard-required columns always exist
    for col in [
        "ego_speed", "overlap",
        "impact_speed", "stop_distance", "t_aeb",
        "aeb_activation", "result_code",
    ]:
        if col not in df.columns:
            df[col] = None

    # Pandas 2.x safe numeric coercion
    for c in df.columns:
        if df[c].dtype == object and c not in ("scenario_name", "status", "state", "date"):
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df["pass_flag"] = df["pass_flag"].fillna(False).astype(bool)
    df["status"] = df["status"].fillna("Unknown")
    df["state"] = df["state"].fillna("Error")

    return df, {"mode": "authoritative + inferred"}
