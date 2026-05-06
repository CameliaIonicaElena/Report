import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm, probplot

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("SPC Dashboard")

# =========================
# LOAD DATA
# =========================
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
df_meas, df_specs = load_data(files[selected])

# =========================
# TRANSFORM
# =========================
df_meas["DATE"] = pd.to_datetime(df_meas["DATE"])

df_long = df_meas.melt(
    id_vars=["DATE", "RAW MATERIAL", "COLOR", "CAV"],
    var_name="Characteristic",
    value_name="Value"
)

df = df_long.merge(df_specs, on="Characteristic", how="left")

# =========================
# FILTERS
# =========================
st.sidebar.header("Filters")

# DATE RANGE
min_d, max_d = df["DATE"].min(), df["DATE"].max()

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(min_d.date(), max_d.date())
)

start_date = pd.to_datetime(start_date)
end_date = pd.to_datetime(end_date)

df = df[df["DATE"].between(start_date, end_date)]

# RAW MATERIAL
materials = sorted(df["RAW MATERIAL"].dropna().unique())
all_m = st.sidebar.checkbox("Select all RAW MATERIAL", True)
sel_m = materials if all_m else st.sidebar.multiselect("RAW MATERIAL", materials)
if sel_m:
    df = df[df["RAW MATERIAL"].isin(sel_m)]

# COLOR
colors = sorted(df["COLOR"].dropna().unique())
all_c = st.sidebar.checkbox("Select all COLOR", True)
sel_c = colors if all_c else st.sidebar.multiselect("COLOR", colors)
if sel_c:
    df = df[df["COLOR"].isin(sel_c)]

# =========================
# LIMITS
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

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Std"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Xbar"]) / (3 * stats["Std"]),
    (stats["Xbar"] - stats["LSL"]) / (3 * stats["Std"])
)

# =========================
# SELECT CHARACTERISTIC
# =========================
char = st.selectbox("Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]["Value"].dropna()
spec = stats[stats["Characteristic"] == char].iloc[0]

# =========================================================
# TOP LAYOUT: CONTROL + HISTOGRAM + MR + CAPABILITY
# =========================================================
st.subheader("Process Analysis")

col1, col2, col3 = st.columns(3)

# =========================
# CONTROL CHART (I)
# =========================
with col1:
    fig, ax = plt.subplots(figsize=(5, 4))

    mean = data.mean()
    mr = data.diff().abs().dropna()

    sigma = mr.mean() / 1.128 if len(mr) > 0 else 0

    UCL = mean + 3 * sigma
    LCL = mean - 3 * sigma

    ax.plot(data.values, marker="o")
    ax.axhline(mean, color="green")
    ax.axhline(UCL, color="red", linestyle="--")
    ax.axhline(LCL, color="red", linestyle="--")

    ax.set_title("I Chart")
    ax.grid()

    st.pyplot(fig)

# =========================
# HISTOGRAM + NORMAL CURVE
# =========================
with col2:
    fig, ax = plt.subplots(figsize=(5, 4))

    ax.hist(data, bins=20, density=True, alpha=0.6)

    if len(data) > 1:
        x = np.linspace(data.min(), data.max(), 100)
        ax.plot(x, norm.pdf(x, data.mean(), data.std()), color="red")

    ax.axvline(spec["USL"], color="red", linestyle="--")
    ax.axvline(spec["LSL"], color="red", linestyle="--")

    ax.set_title("Histogram + Normal")
    ax.grid()

    st.pyplot(fig)

# =========================
# MOVING RANGE
# =========================
with col3:
    fig, ax = plt.subplots(figsize=(5, 4))

    mr = data.diff().abs().dropna()

    ax.plot(mr.values, marker="o", color="orange")

    mr_mean = mr.mean() if len(mr) > 0 else 0
    MR_UCL = mr_mean * 3.267

    ax.axhline(mr_mean, color="green")
    ax.axhline(MR_UCL, color="red", linestyle="--")

    ax.set_title("Moving Range")
    ax.grid()

    st.pyplot(fig)

# =========================================================
# MIDDLE: CAPABILITY + NORMAL PROB PLOT
# =========================================================
st.subheader("Capability & Distribution")

col4, col5 = st.columns(2)

# =========================
# CAPABILITY BAR
# =========================
with col4:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.bar(["Cp", "Cpk"], [spec["Cp"], spec["Cpk"]], color=["blue", "orange"])
    ax.axhline(1.33, color="red", linestyle="--")

    ax.set_title("Capability (Cp / Cpk)")
    ax.grid()

    st.pyplot(fig)

# =========================
# NORMAL PROBABILITY PLOT
# =========================
with col5:
    fig, ax = plt.subplots(figsize=(6, 4))

    probplot(data, dist="norm", plot=ax)

    ax.set_title("Normal Probability Plot")
    ax.grid()

    st.pyplot(fig)

# =========================================================
# BOTTOM: SUMMARY STATS
# =========================================================
st.subheader("Summary Statistics")

summary = pd.DataFrame({
    "Mean": [data.mean()],
    "Std": [data.std()],
    "Min": [data.min()],
    "Max": [data.max()],
    "Cp": [spec["Cp"]],
    "Cpk": [spec["Cpk"]]
})

st.dataframe(summary, use_container_width=True)
