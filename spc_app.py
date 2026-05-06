import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

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

df = df_meas.melt(
    id_vars=["DATE", "RAW MATERIAL", "COLOR", "CAV"],
    var_name="Characteristic",
    value_name="Value"
).merge(df_specs, on="Characteristic", how="left")

# =========================
# FILTERS
# =========================
st.sidebar.header("Filters")

min_d, max_d = df["DATE"].min(), df["DATE"].max()

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(min_d, max_d),
    min_value=min_d,
    max_value=max_d
)

df = df[df["DATE"].between(pd.to_datetime(start_date), pd.to_datetime(end_date))]

materials = sorted(df["RAW MATERIAL"].dropna().unique())
if st.sidebar.checkbox("Select all RAW MATERIAL", True):
    selected_m = materials
else:
    selected_m = st.sidebar.multiselect("RAW MATERIAL", materials)

df = df[df["RAW MATERIAL"].isin(selected_m)]

colors = sorted(df["COLOR"].dropna().unique())
if st.sidebar.checkbox("Select all COLOR", True):
    selected_c = colors
else:
    selected_c = st.sidebar.multiselect("COLOR", colors)

df = df[df["COLOR"].isin(selected_c)]

# =========================
# SPEC LIMITS
# =========================
df["USL"] = df["Target"] + df["Upper Dev"]
df["LSL"] = df["Target"] + df["Lower Dev"]

# =========================
# STATS PER CHARACTERISTIC
# =========================
g = df.groupby("Characteristic")

stats = pd.DataFrame({
    "Characteristic": g["Value"].mean().index,
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

# OOS
above = df[df["Value"] > df["USL"]].groupby("Characteristic")["Value"].count()
below = df[df["Value"] < df["LSL"]].groupby("Characteristic")["Value"].count()

stats["Above OOS"] = stats["Characteristic"].map(above).fillna(0).astype(int)
stats["Below OOS"] = stats["Characteristic"].map(below).fillna(0).astype(int)

# =========================
# SUMMARY (IMPORTANT POSITION)
# =========================
st.subheader("📌 Summary KPIs")
st.dataframe(stats, use_container_width=True)

# =========================
# SELECT CHARACTERISTIC
# =========================
char = st.selectbox("Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

# ==========================================================
# 🔎 LOCAL ANALYSIS (PER CHARACTERISTIC)
# ==========================================================
st.markdown("## 🔎 Characteristic Analysis")

c1, c2 = st.columns(2)

# CONTROL CHART
with c1:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.plot(values.values, marker="o")
    ax.axhline(spec["Xbar"], color="green", label="Mean")
    ax.axhline(spec["USL"], color="red")
    ax.axhline(spec["LSL"], color="red")

    ax.set_title("Control Chart")
    ax.grid()
    ax.legend()

    st.pyplot(fig)

# HISTOGRAM + NORMAL
with c2:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.hist(values, bins=20, density=True, alpha=0.6)

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        ax.plot(x, norm.pdf(x, values.mean(), values.std()), color="red")

    ax.set_title("Histogram + Normal Curve")
    ax.grid()

    st.pyplot(fig)

# =========================
# SECOND ROW
# =========================
c3, c4 = st.columns(2)

# MOVING RANGE
with c3:
    if len(values) > 1:
        mr = values.diff().abs().dropna()

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(mr.values, marker="o", color="orange")
        ax.axhline(mr.mean(), color="green", label="MR Mean")

        ax.set_title("Moving Range Chart")
        ax.grid()
        ax.legend()

        st.pyplot(fig)
    else:
        st.warning("Not enough data for MR")

# CAPABILITY
with c4:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.bar(["Cp", "Cpk"], [spec["Cp"], spec["Cpk"]], color=["blue", "purple"])
    ax.axhline(1.33, color="red", linestyle="--")

    ax.set_title("Capability (Cp / Cpk)")
    ax.grid()

    st.pyplot(fig)

# =========================
# GLOBAL ANALYSIS (SEPARATE SECTION)
# =========================
st.markdown("---")
st.markdown("## 🌍 Global Overview (All Characteristics)")

c5, c6 = st.columns(2)

# BOX PLOT
with c5:
    fig, ax = plt.subplots(figsize=(7, 5))

    df.boxplot(column="Value", by="Characteristic", ax=ax)
    ax.set_title("Boxplot per Characteristic")
    ax.set_xlabel("")
    plt.xticks(rotation=45)

    st.pyplot(fig)

# PARETO OOS
with c6:
    oos = stats[["Characteristic", "Above OOS", "Below OOS"]].copy()
    oos["Total OOS"] = oos["Above OOS"] + oos["Below OOS"]
    oos = oos.sort_values("Total OOS", ascending=False)

    fig, ax = plt.subplots(figsize=(7, 5))

    ax.bar(oos["Characteristic"], oos["Total OOS"], color="darkred")
    ax.set_title("Pareto OOS")
    ax.set_xticklabels(oos["Characteristic"], rotation=45)

    st.pyplot(fig)
