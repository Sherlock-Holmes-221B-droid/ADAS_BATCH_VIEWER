import streamlit as st
import pandas as pd
from typing import Optional
from parser import parse_report
from bs4 import BeautifulSoup
# ============================================================
# Page configuration
# ============================================================

st.set_page_config(
    page_title="ADAS Batch Viewer",
    layout="wide",
)

st.title("ADAS Batch Viewer")

# ============================================================
# SAFE DataFrame renderer (Cloud + Local compatible)
# ============================================================
def parse_report_from_string(html_text: str):
    """
    Adapter that allows parser.py to work with Streamlit UploadedFile.
    """
    from parser import parse_report
    import tempfile

    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=True, mode="w", encoding="utf-8"
    ) as tmp:
        tmp.write(html_text)
        tmp.flush()
        return parse_report(tmp.name)
    
def safe_dataframe(df: pd.DataFrame, *, height: Optional[int] = None) -> None:
    """
    Render DataFrame safely on Streamlit Cloud and locally.

    Fixes:
    - blank tables on Streamlit Cloud
    - duplicate column Arrow crashes
    - all-NaN rows/columns
    - mutation across reruns
    """
    if df is None or df.empty:
        st.info("No data available.")
        return

    df_view = df.copy()

    # Drop empty rows / columns
    df_view = df_view.dropna(axis=1, how="all")
    df_view = df_view.dropna(axis=0, how="all")

    # Remove duplicate column names (CRITICAL)
    df_view = df_view.loc[:, ~df_view.columns.duplicated()]

    st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True,
        height=height,
    )

# ============================================================
# Load & cache parsed data
# ============================================================

@st.cache_data(show_spinner=True)
def load_data(uploaded_file) -> pd.DataFrame:
    """
    Streamlit uploader returns UploadedFile, not a file path.
    Convert to HTML text before passing to parser.
    """
    html_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    df, _ = parse_report_from_string(html_text)
    return df.copy()


# ============================================================
# File upload
# ============================================================

uploaded_html = st.sidebar.file_uploader(
    "Upload batch report HTML",
    type=["html", "htm"],
)

if uploaded_html is None:
    st.info("Please upload a batch HTML report.")
    st.stop()

df_all = load_data(uploaded_html)

# ============================================================
# Global numeric normalization (pandas 2.x safe)
# ============================================================

NUMERIC_COLUMNS = [
    "ego_speed",
    "overlap",
    "impact_speed",
    "stop_distance",
    "t_aeb",
    "aeb_activation",
    "result_code",
    "real_duration",
    "real_time_ratio",
    "sim_duration",
]

for col in NUMERIC_COLUMNS:
    if col in df_all.columns:
        df_all[col] = pd.to_numeric(df_all[col], errors="coerce")

# Never mutate cached DataFrame across reruns
df_all = df_all.copy()

# ============================================================
# Sidebar: Scenario selection
# ============================================================

scenario_list = ["All Scenarios"] + sorted(
    df_all["scenario_name"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

selected_scenario = st.sidebar.selectbox(
    "Select Scenario",
    scenario_list,
)

# ============================================================
# ALL SCENARIOS VIEW
# ============================================================

if selected_scenario == "All Scenarios":
    st.subheader("All Scenarios")

    summary_columns = [
        "scenario_name",
        "state",
        "status",
        "ego_speed",
        "overlap",
        "impact_speed",
        "stop_distance",
        "t_aeb",
        "aeb_activation",
        "result_code",
        "date",
    ]

    available_columns = [c for c in summary_columns if c in df_all.columns]
    df_summary = df_all[available_columns]

    safe_dataframe(df_summary)

    st.stop()

# ============================================================
# SINGLE SCENARIO VIEW
# ============================================================

df_scenario = df_all[df_all["scenario_name"] == selected_scenario].copy()

if df_scenario.empty:
    st.warning("Selected scenario has no data.")
    st.stop()

row = df_scenario.iloc[0]

st.subheader(f"Scenario: {selected_scenario}")

# ------------------------------------------------------------
# KPI section
# ------------------------------------------------------------

kpi_cols = st.columns(3)

kpi_cols[0].metric(
    "Impact speed (m/s)",
    f"{row['impact_speed']:.3f}" if pd.notna(row.get("impact_speed")) else "—",
)

kpi_cols[1].metric(
    "T_AEB (s)",
    f"{row['t_aeb']:.3f}" if pd.notna(row.get("t_aeb")) else "—",
)

kpi_cols[2].metric(
    "AEB activation",
    f"{int(row['aeb_activation'])}" if pd.notna(row.get("aeb_activation")) else "—",
)

st.markdown("---")

# ------------------------------------------------------------
# Scenario details table
# ------------------------------------------------------------

st.markdown("### Scenario Details")

safe_dataframe(df_scenario, height=420)
