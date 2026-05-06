import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

# =========================
# CONFIG (MUST BE FIRST)
# =========================
st.set_page_config(layout="wide")
st.title("SPC Dashboard")

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=86400)
def load_data(file):
    df_meas = pd.read_excel(file, sheet_name="Measurements")
    df_specs = pd.read_excel(file, sheet_name="Specs")

    df_meas.columns = df_meas.columns.str.strip()
    df_specs.columns = df_specs.columns.str.strip()

    return df_meas, df_specs


files = {
    "Dataset 0": "Test-Measurements&Specs.xlsx",
    "Dataset 1": "Test-Measurements&Specs1.xlsx",
    "Dataset 2": "Test-Measurements&Specs2.xlsx"
}

selected = st.sidebar.selectbox("Select dataset", list(files.keys()))
file_path = files[selected]

df_meas, df_specs = load_data(file_path)

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

# force numeric safety
df["Value"] = pd.to_numeric(df["Value"], errors="coerce")

df = df.dropna(subset=["DATE", "Value"])

# =========================
# FILTERS
# =========================
st.sidebar.header("Filters")

# DATE RANGE (ONLY ONCE)
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

# =========================
# RAW MATERIAL
# =========================
materials = sorted(df["RAW MATERIAL"].dropna().unique())

select_all_m = st.sidebar.checkbox("Select all RAW MATERIAL", value=True)

if select_all_m:
    selected_m = materials
else:
    selected_m = st.sidebar.multiselect("RAW MATERIAL", materials)

if selected_m:
    df = df[df["RAW MATERIAL"].isin(selected_m)]

# =========================
# COLOR
# =========================
colors = sorted(df["COLOR"].dropna().unique())

select_all_c = st.sidebar.checkbox("Select all COLOR", value=True)

if select_all_c:
    selected_c = colors
else:
    selected_c = st.sidebar.multiselect("COLOR", colors)

if selected_c:
    df = df[df["COLOR"].isin(selected_c)]

# =========================
# SPEC LIMITS
# =========================
df["USL"] = df["Target"] + df["Upper Dev"]
df["LSL"] = df["Target"] + df["Lower Dev"]

# =========================
# STATS
# =========================
g = df.groupby("Characteristic")

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

# safety std
stats["Std"] = stats["Std"].replace(0, np.nan)

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
    if x >= 1.67:
        return "Excellent"
    if x >= 1.33:
        return "Capable"
    if x >= 1.0:
        return "Marginal"
    return "Not capable"

stats["Capability"] = stats["Cpk"].apply(cap)

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
# CHARACTERISTIC
# =========================
char = st.selectbox("Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

# =========================
# CHARTS LAYOUT (2x2 clean)
# =========================
st.subheader("Charts")

col1, col2 = st.columns(2)

with col1:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(values.values, marker="o")
    ax.axhline(spec["Xbar"], color="green")
    ax.axhline(spec["USL"], color="red")
    ax.axhline(spec["LSL"], color="red")
    ax.set_title("Control Chart")
    ax.grid()
    st.pyplot(fig)

with col2:
    fig2, ax2 = plt.subplots(figsize=(6, 4))
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

    fig, ax = plt.subplots(2, 1, figsize=(12, 5), sharex=True)

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
    st.warning("Not enough data")
