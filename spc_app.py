import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
import os

# =========================
# CONFIG (FIRST)
# =========================
st.set_page_config(layout="wide")
st.title("SPC Dashboard")

# =========================
# CACHE LOAD (AUTO REFRESH 24h)
# =========================
@st.cache_data(ttl=86400)
def load_data(file):
    df_meas = pd.read_excel(file, sheet_name="Measurements")
    df_specs = pd.read_excel(file, sheet_name="Specs")

    df_meas.columns = df_meas.columns.str.strip()
    df_specs.columns = df_specs.columns.str.strip()

    return df_meas, df_specs

# =========================
# DATASETS
# =========================
BASE_DIR = os.path.dirname(__file__)

files = {
    "Dataset Original": os.path.join(BASE_DIR, "Test-Measurements&Specs.xlsx"),
    "Dataset Test1": os.path.join(BASE_DIR, "Test-Measurements&Specs1.xlsx"),
    "Dataset Test2": os.path.join(BASE_DIR, "Test-Measurements&Specs2.xlsx")
}

selected_dataset = st.sidebar.selectbox("Select dataset", list(files.keys()))
file = files[selected_dataset]

# 🔄 MANUAL REFRESH
if st.sidebar.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()

# =========================
# FILE CHECK
# =========================
if not os.path.exists(file):
    st.error(f"Missing file: {file}")
    st.stop()

# =========================
# LOAD DATA (CORECT)
# =========================
df_meas, df_specs = load_data(file)

# =========================
# TRANSFORM
# =========================
df_long = df_meas.melt(
    id_vars=["DATE", "RAW MATERIAL", "COLOR", "CAV"],
    var_name="Characteristic",
    value_name="Value"
)

df = df_long.merge(df_specs, on="Characteristic", how="left")
df["DATE"] = pd.to_datetime(df["DATE"])

if df.empty:
    st.error("Dataset empty after merge")
    st.stop()

# =========================
# FILTERS
# =========================
st.sidebar.header("Filters")

df_filtered = df.copy()

# DATE RANGE
min_date = df["DATE"].min()
max_date = df["DATE"].max()

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

df_filtered = df_filtered[
    (df_filtered["DATE"] >= pd.to_datetime(start_date)) &
    (df_filtered["DATE"] <= pd.to_datetime(end_date))
]

# RAW MATERIAL
materials = sorted(df["RAW MATERIAL"].dropna().unique())
select_all_m = st.sidebar.checkbox("Select all RAW MATERIAL", value=True)

selected_materials = materials if select_all_m else st.sidebar.multiselect("RAW MATERIAL", materials)

if selected_materials:
    df_filtered = df_filtered[df_filtered["RAW MATERIAL"].isin(selected_materials)]

# COLOR
colors = sorted(df["COLOR"].dropna().unique())
select_all_c = st.sidebar.checkbox("Select all COLOR", value=True)

selected_colors = colors if select_all_c else st.sidebar.multiselect("COLOR", colors)

if selected_colors:
    df_filtered = df_filtered[df_filtered["COLOR"].isin(selected_colors)]

# =========================
# LIMITS
# =========================
df_filtered["USL"] = df_filtered["Target"] + df_filtered["Upper Dev"]
df_filtered["LSL"] = df_filtered["Target"] + df_filtered["Lower Dev"]

# =========================
# STATS
# =========================
g = df_filtered.groupby("Characteristic")

stats = pd.DataFrame({
    "Characteristic": g["Characteristic"].first(),
    "USL": g["USL"].first(),
    "LSL": g["LSL"].first(),
    "Xbar": g["Value"].mean(),
    "Std": g["Value"].std(),
    "Max": g["Value"].max(),
    "Min": g["Value"].min(),
    "Count": g["Value"].count()
}).reset_index(drop=True)

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Std"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Xbar"]) / (3 * stats["Std"]),
    (stats["Xbar"] - stats["LSL"]) / (3 * stats["Std"])
)

# =========================
# OOS
# =========================
above = df_filtered[df_filtered["Value"] > df_filtered["USL"]].groupby("Characteristic")["Value"].count()
below = df_filtered[df_filtered["Value"] < df_filtered["LSL"]].groupby("Characteristic")["Value"].count()

stats["Above OOS"] = stats["Characteristic"].map(above).fillna(0).astype(int)
stats["Below OOS"] = stats["Characteristic"].map(below).fillna(0).astype(int)

# =========================
# STYLE
# =========================
def highlight(df):
    style = pd.DataFrame("", index=df.index, columns=df.columns)
    style.loc[df["Above OOS"] > 0, "Above OOS"] = "color:red; font-weight:bold"
    style.loc[df["Below OOS"] > 0, "Below OOS"] = "color:red; font-weight:bold"
    return style

# =========================
# TABLE
# =========================
st.subheader("SPC Summary")
st.dataframe(stats.style.apply(highlight, axis=None), use_container_width=True)

# =========================
# SELECT CHAR
# =========================
char = st.selectbox("Select Characteristic", stats["Characteristic"])

data = df_filtered[df_filtered["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

# =========================
# CHARTS
# =========================
col1, col2 = st.columns(2)

# CONTROL
with col1:
    fig, ax = plt.subplots()
    ax.plot(values.values, marker="o")
    ax.axhline(spec["Xbar"])
    ax.axhline(spec["USL"])
    ax.axhline(spec["LSL"])
    ax.set_title("Control Chart")
    st.pyplot(fig)

# HISTOGRAM
with col2:
    fig2, ax2 = plt.subplots()
    ax2.hist(values, bins=20, density=True)

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        y = norm.pdf(x, values.mean(), values.std())
        ax2.plot(x, y)

    ax2.set_title("Histogram")
    st.pyplot(fig2)

# =========================
# I-MR
# =========================
if len(values) > 1:
    mean = values.mean()
    mr = values.diff().abs().dropna()
    sigma = mr.mean() / 1.128

    UCL = mean + 3 * sigma
    LCL = mean - 3 * sigma

    fig, ax = plt.subplots(2, 1, sharex=True)

    ax[0].plot(values.values, marker="o")
    ax[0].axhline(mean)
    ax[0].axhline(UCL, linestyle="--")
    ax[0].axhline(LCL, linestyle="--")

    ax[1].plot(mr.values, marker="o")
    ax[1].axhline(mr.mean())
    ax[1].axhline(mr.mean() * 3.267, linestyle="--")

    st.pyplot(fig)
