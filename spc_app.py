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
# BASE PATH (ONE DRIVE LOCAL)
# =========================
BASE_PATH = r"C:\Users\RO10471\OneDrive - SIG\GQM spouts - Documents\Measurements-test files"

# =========================
# DATASETS
# =========================
files = {
    "Dataset Original": "Test-Measurements&Specs.xlsx",
    "Dataset Test1": "Test-Measurements&Specs1.xlsx",
    "Dataset Test2": "Test-Measurements&Specs2.xlsx"
}

selected_dataset = st.sidebar.selectbox("Select dataset", list(files.keys()))
file_path = os.path.join(BASE_PATH, files[selected_dataset])

# =========================
# FILE CHECK
# =========================
if not os.path.exists(file_path):
    st.error(f"File not found:\n{file_path}")
    st.stop()

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=86400)
def load_data(path):
    df_meas = pd.read_excel(path, sheet_name="Measurements")
    df_specs = pd.read_excel(path, sheet_name="Specs")

    df_meas.columns = df_meas.columns.str.strip()
    df_specs.columns = df_specs.columns.str.strip()

    return df_meas, df_specs

df_meas, df_specs = load_data(file_path)

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

# =========================
# FILTERS
# =========================
st.sidebar.header("Filters")

df_filtered = df.copy()

# DATE RANGE
min_date = df_filtered["DATE"].min()
max_date = df_filtered["DATE"].max()

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
materials = sorted(df_filtered["RAW MATERIAL"].dropna().unique())
if st.sidebar.checkbox("Select all RAW MATERIAL", True):
    selected_materials = materials
else:
    selected_materials = st.sidebar.multiselect("RAW MATERIAL", materials)

df_filtered = df_filtered[df_filtered["RAW MATERIAL"].isin(selected_materials)]

# COLOR
colors = sorted(df_filtered["COLOR"].dropna().unique())
if st.sidebar.checkbox("Select all COLOR", True):
    selected_colors = colors
else:
    selected_colors = st.sidebar.multiselect("COLOR", colors)

df_filtered = df_filtered[df_filtered["COLOR"].isin(selected_colors)]

# =========================
# SPEC LIMITS
# =========================
df_filtered["USL"] = df_filtered["Target"] + df_filtered["Upper Dev"]
df_filtered["LSL"] = df_filtered["Target"] + df_filtered["Lower Dev"]

# =========================
# STATS
# =========================
g = df_filtered.groupby("Characteristic")

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
above = df_filtered[df_filtered["Value"] > df_filtered["USL"]].groupby("Characteristic")["Value"].count()
below = df_filtered[df_filtered["Value"] < df_filtered["LSL"]].groupby("Characteristic")["Value"].count()

stats["Above OOS"] = stats["Characteristic"].map(above).fillna(0).astype(int)
stats["Below OOS"] = stats["Characteristic"].map(below).fillna(0).astype(int)

# =========================
# CAPABILITY
# =========================
def capability(x):
    if pd.isna(x):
        return "No data"
    elif x >= 1.67:
        return "Excellent"
    elif x >= 1.33:
        return "Capable"
    elif x >= 1.0:
        return "Marginal"
    return "Not capable"

stats["Capability"] = stats["Cpk"].apply(capability)
stats["OK"] = np.where(stats["Cpk"] >= 1.33, "YES", "NO")

# =========================
# STYLE (RED + BOLD OOS)
# =========================
def highlight(df):
    style = pd.DataFrame("", index=df.index, columns=df.columns)
    style.loc[df["Above OOS"] > 0, "Above OOS"] = "color:red;font-weight:bold"
    style.loc[df["Below OOS"] > 0, "Below OOS"] = "color:red;font-weight:bold"
    return style

# =========================
# TABLE
# =========================
st.subheader("SPC Summary")
st.dataframe(stats.style.apply(highlight, axis=None), use_container_width=True)

# =========================
# CHARACTERISTIC
# =========================
char = st.selectbox("Select Characteristic", stats["Characteristic"])

data = df_filtered[df_filtered["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

# =========================
# CHART LAYOUT 2x2 WIDE
# =========================
st.subheader("Charts")

col1, col2 = st.columns(2)

# CONTROL CHART
with col1:
    fig, ax = plt.subplots()
    ax.plot(values.values, marker="o")
    ax.axhline(spec["Xbar"], color="green")
    ax.axhline(spec["USL"], color="red")
    ax.axhline(spec["LSL"], color="red")
    ax.set_title("Control Chart")
    ax.grid()
    st.pyplot(fig)

# HISTOGRAM
with col2:
    fig2, ax2 = plt.subplots()
    ax2.hist(values, bins=20, density=True, alpha=0.6)

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        y = norm.pdf(x, values.mean(), values.std())
        ax2.plot(x, y, color="red")

    ax2.set_title("Histogram")
    ax2.grid()
    st.pyplot(fig2)

# =========================
# I-MR CHART
# =========================
st.subheader("I-MR Chart")

if len(values) > 1:

    mean = values.mean()
    mr = values.diff().abs().dropna()

    sigma = mr.mean() / 1.128

    UCL = mean + 3 * sigma
    LCL = mean - 3 * sigma

    fig, ax = plt.subplots(2, 1, figsize=(14, 5), sharex=True)

    ax[0].plot(values.values, marker="o")
    ax[0].axhline(mean, color="green")
    ax[0].axhline(UCL, color="red", linestyle="--")
    ax[0].axhline(LCL, color="red", linestyle="--")
    ax[0].grid()

    MR_UCL = mr.mean() * 3.267

    ax[1].plot(mr.values, marker="o", color="orange")
    ax[1].axhline(mr.mean(), color="green")
    ax[1].axhline(MR_UCL, color="red", linestyle="--")
    ax[1].grid()

    st.pyplot(fig)

else:
    st.warning("Not enough data for I-MR chart")
