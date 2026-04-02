# HtmltoReport.py
# ============================================================
# ADAS Batch Viewer – Cloud & Local SAFE version
# - Table-only UI
# - Table-only PPT export
# - No Plotly / Kaleido / AgGrid
# ============================================================

import io
import os
import tempfile
import streamlit as st
import pandas as pd
from parser import parse_report
from pptx import Presentation
from pptx.util import Inches, Pt

# ============================================================
# Page config
# ============================================================

st.set_page_config(
    page_title="ADAS Batch Viewer",
    layout="wide"
)
st.title("ADAS Batch Viewer")

# ============================================================
# Helpers
# ============================================================

def safe_dataframe(df: pd.DataFrame, height: int = 420):
    """
    Cloud-safe DataFrame rendering
    """
    if df is None or df.empty:
        st.info("No data available.")
        return

    df_view = df.copy()
    df_view = df_view.dropna(axis=1, how="all")
    df_view = df_view.dropna(axis=0, how="all")
    df_view = df_view.loc[:, ~df_view.columns.duplicated()]

    st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True,
        height=height
    )

def export_ppt_tables_only(df: pd.DataFrame) -> bytes:
    """
    Build PPT with TABLES ONLY (no images, no charts)
    Cloud safe (python-pptx only)
    """
    prs = Presentation()

    # ---------------- Title slide ----------------
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "ADAS Batch Report"
    slide.placeholders[1].text = "Generated from batch HTML"

    # ---------------- Summary slide ----------------
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Summary"

    total = len(df)
    passed = int(df["state"].eq("Pass").sum()) if "state" in df else 0
    failed = int(df["state"].eq("Fail").sum()) if "state" in df else 0

    tf = slide.shapes.add_textbox(
        Inches(0.8), Inches(1.2), Inches(4), Inches(3)
    ).text_frame

    tf.text = (
        f"Total Scenarios: {total}\n"
        f"Passed: {passed}\n"
        f"Failed: {failed}\n"
        f"Pass Rate: {passed/total:.0%}" if total else "No data"
    )

    # ---------------- All Scenarios table ----------------
    show_cols = [
        "scenario_name", "state", "status",
        "ego_speed", "overlap",
        "impact_speed", "stop_distance", "t_aeb",
        "aeb_activation", "result_code"
    ]
    cols = [c for c in show_cols if c in df.columns]
    table_df = df[cols].copy()

    rows_per_slide = 18
    start = 0

    while start < len(table_df):
        chunk = table_df.iloc[start:start + rows_per_slide]

        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = f"All Scenarios ({start+1}-{start+len(chunk)})"

        rows = len(chunk) + 1
        cols_n = len(cols)

        table = slide.shapes.add_table(
            rows, cols_n,
            Inches(0.4), Inches(1.2),
            Inches(9.2), Inches(5.0)
        ).table

        # Header
        for j, col in enumerate(cols):
            cell = table.cell(0, j)
            cell.text = col.replace("_", " ").title()
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(12)
                p.font.bold = True

        # Data
        for i, row in enumerate(chunk.itertuples(index=False), start=1):
            for j, col in enumerate(cols):
                val = getattr(row, col)
                table.cell(i, j).text = "" if pd.isna(val) else str(val)

        start += rows_per_slide

    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()


# ============================================================
# Load HTML (UploadedFile → temp path → parser)
# ============================================================

@st.cache_data(show_spinner=True)
def load_data(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        tmp.write(uploaded_file.getvalue())
        path = tmp.name

    res = parse_report(path)
    df = res[0] if isinstance(res, tuple) else res

    if "state" not in df.columns and "status" in df.columns:
        df["state"] = df["status"].apply(
            lambda x: x if x in ("Pass", "Fail") else "Error"
        )

    return df.copy()

# ============================================================
# UI
# ============================================================

uploaded = st.file_uploader("Upload batch HTML", type=["html", "htm"])

if not uploaded:
    st.info("Please upload a batch HTML report.")
    st.stop()

df_all = load_data(uploaded)

# Numeric normalization
for c in df_all.columns:
    if c not in ("scenario_name", "status", "state", "date"):
        df_all[c] = pd.to_numeric(df_all[c], errors="coerce")

# Scenario selection
scenarios = ["All Scenarios"] + sorted(
    df_all["scenario_name"].dropna().unique().tolist()
)
selected = st.selectbox("Select Scenario", scenarios)

# ============================================================
# Views
# ============================================================

if selected == "All Scenarios":
    st.subheader("All Scenarios")
    safe_dataframe(df_all)

else:
    df_s = df_all[df_all["scenario_name"] == selected].copy()
    st.subheader(f"Scenario: {selected}")
    safe_dataframe(df_s)

# ============================================================
# Export
# ============================================================

st.subheader("Export")

if st.button("Export PowerPoint (tables only)"):
    ppt_bytes = export_ppt_tables_only(df_all)
    st.download_button(
        "Download PPTX",
        ppt_bytes,
        file_name="ADAS_Batch_Report.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
