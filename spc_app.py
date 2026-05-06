import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
import os

# =========================
# CONFIG (MUST BE FIRST)
# =========================
st.set_page_config(layout="wide")
st.title("SPC Dashboard")

# =========================
# LOAD DATA (FROM REPO)
# =========================
BASE_DIR = os.path.dirname(__file__)

files = {
    "Dataset 0": os.path.join(BASE_DIR, "Test-Measurements&Specs.xlsx"),
    "Dataset 1": os.path.join(BASE_DIR, "Test-Measurements&Specs1.xlsx"),
    "Dataset 2": os.path.join(BASE_DIR, "Test-Measurements&Specs2.xlsx")
}

selected_file = st.sidebar.selectbox("Select dataset", list(files.keys()))
file_path = files[selected_file]

if not os.path.exists(file_path):
    st.error(f"Missing file: {file_path}")
    st.stop()

df_meas = pd.read_excel(file_path, sheet_name="Measurements")
df_specs = pd.read_excel(file_path, sheet_name="Specs")

df_meas.columns = df_meas.columns.str.strip()
df_specs.columns = df_specs.columns.str.strip()

# =========================
# TRANSFORM
# =========================
df_meas["DATE"] = pd.to_datetime(df_meas["DATE"], errors="coerce")

df_long = df_meas.melt(
    id_vars=["DATE", "RAW MATERIAL", "COLOR", "CAV"],
    var_name="Characteristic",
    value_name="Value"
)

df = df_long.merge(df_specs, on="Characteristic", how="left")

df["USL"] = df["Target"] + df["Upper Dev"]
df["LSL"] = df["Target"] + df["Lower Dev"]

df = df.dropna(subset=["DATE", "Value"])

# =========================
# FILTERS
# =========================
st.sidebar.header("Filters")

# DATE RANGE
min_d = df["DATE"].min().date()
max_d = df["DATE"].max().date()

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(min_d, max_d),
    min_value=min_d,
    max_value=max_d
)

start_date = pd.to_datetime(start_date)
end_date = pd.to_datetime(end_date)

df = df[df["DATE"].between(start_date, end_date)]

# RAW MATERIAL
materials = sorted(df["RAW MATERIAL"].dropna().unique())
select_all_m = st.sidebar.checkbox("Select all RAW MATERIAL", value=True)

selected_m = materials if select_all_m else st.sidebar.multiselect(
    "RAW MATERIAL", materials
)

if selected_m:
    df = df[df["RAW MATERIAL"].isin(selected_m)]

# COLOR
colors = sorted(df["COLOR"].dropna().unique())
select_all_c = st.sidebar.checkbox("Select all COLOR", value=True)

selected_c = colors if select_all_c else st.sidebar.multiselect(
    "COLOR", colors
)

if selected_c:
    df = df[df["COLOR"].isin(selected_c)]

# =========================
# STATS
# =========================
g = df.groupby("Characteristic")

stats = pd.DataFrame({
    "Characteristic": g["Characteristic"].first(),
    "Upper Dev": g["Upper Dev"].first(),
    "Lower Dev": g["Lower Dev"].first(),
    "USL": g["USL"].first(),
    "LSL": g["LSL"].first(),
    "Xbar": g["Value"].mean(),
    "Std": g["Value"].std(),
    "Max": g["Value"].max(),
    "Min": g["Value"].min(),
    "Count": g["Value"].count()
}).reset_index(drop=True)

# =========================
# METRICS
# =========================
stats["Range"] = stats["Max"] - stats["Min"]
stats["+3s"] = stats["Xbar"] + 3 * stats["Std"]
stats["-3s"] = stats["Xbar"] - 3 * stats["Std"]

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Std"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Xbar"]) / (3 * stats["Std"]),
    (stats["Xbar"] - stats["LSL"]) / (3 * stats["Std"])
)

# =========================
# OOS
# =========================
above = df[df["Value"] > df["USL"]].groupby("Characteristic")["Value"].count()
below = df[df["Value"] < df["LSL"]].groupby("Characteristic")["Value"].count()

stats["Above OOS"] = stats["Characteristic"].map(above).fillna(0).astype(int)
stats["Below OOS"] = stats["Characteristic"].map(below).fillna(0).astype(int)

# =========================
# CAPABILITY
# =========================
def cap(x):
    if pd.isna(x):
        return "No data"
    elif x >= 1.67:
        return "Excellent"
    elif x >= 1.33:
        return "Capable"
    elif x >= 1.0:
        return "Marginal"
    return "Not capable"

stats["Capability"] = stats["Cpk"].apply(cap)
stats["OK"] = np.where(stats["Cpk"] >= 1.33, "YES", "NO")

# =========================
# STYLE (RED + BOLD OOS)
# =========================
def style(df):
    s = pd.DataFrame("", index=df.index, columns=df.columns)
    s.loc[df["Above OOS"] > 0, "Above OOS"] = "color:red;font-weight:bold"
    s.loc[df["Below OOS"] > 0, "Below OOS"] = "color:red;font-weight:bold"
    return s

st.subheader("SPC Summary")
st.dataframe(stats.style.apply(style, axis=None), use_container_width=True)

# =========================
# SELECT CHARACTERISTIC
# =========================
char = st.selectbox("Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna().reset_index(drop=True)

# =========================
# CHART LAYOUT
# =========================
st.subheader("Charts")

col1, col2 = st.columns(2)

# CONTROL CHART
with col1:
    fig, ax = plt.subplots(figsize=(7, 4))

    ax.plot(values.values, marker="o", linewidth=1)
    ax.axhline(spec["Xbar"], color="green")
    ax.axhline(spec["USL"], color="red", linestyle="--")
    ax.axhline(spec["LSL"], color="red", linestyle="--")

    ax.set_title("Control Chart")
    ax.grid()

    st.pyplot(fig)

# RIGHT SIDE
with col2:

    # ================= HISTOGRAM =================
    st.markdown("### Histogram")

    fig2, ax2 = plt.subplots(figsize=(7, 2.5))

    ax2.hist(values, bins=20, density=True, alpha=0.6)

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        y = norm.pdf(x, values.mean(), values.std())
        ax2.plot(x, y, color="red")

    ax2.grid()
    st.pyplot(fig2)

    # ================= MOVING RANGE =================
    st.markdown("### Moving Range")

    if len(values) > 1:

        mr = values.diff().abs().dropna()
        mr_mean = mr.mean()
        mr_ucl = mr_mean * 3.267

        fig3, ax3 = plt.subplots(figsize=(7, 2.5))

        ax3.plot(mr.values, marker="o", color="orange", linewidth=1)
        ax3.axhline(mr_mean, color="green", label="Mean")
        ax3.axhline(mr_ucl, color="red", linestyle="--", label="UCL")

        ax3.set_title("MR Chart")
        ax3.grid()
        ax3.legend()

        st.pyplot(fig3)

    else:
        st.warning("Not enough data for MR")
