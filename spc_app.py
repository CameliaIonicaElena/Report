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
# DATASETS
# =========================
files = {
    "Dataset 0": "Test-Measurements&Specs.xlsx",
    "Dataset 1": "Test-Measurements&Specs1.xlsx",
    "Dataset 2": "Test-Measurements&Specs2.xlsx"
}

selected_file = st.sidebar.selectbox("Select dataset", list(files.keys()))
file_path = files[selected_file]

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
df = df.dropna(subset=["Value", "DATE"])

# =========================
# FILTERS
# =========================
st.sidebar.header("Filters")

min_d = df["DATE"].min()
max_d = df["DATE"].max()

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(min_d.date(), max_d.date()),
    min_value=min_d.date(),
    max_value=max_d.date()
)

start_date = pd.to_datetime(start_date)
end_date = pd.to_datetime(end_date)

df = df[df["DATE"].between(start_date, end_date)]

# RAW MATERIAL
materials = sorted(df["RAW MATERIAL"].dropna().unique())
if st.sidebar.checkbox("Select all RAW MATERIAL", True):
    selected_m = materials
else:
    selected_m = st.sidebar.multiselect("RAW MATERIAL", materials)

df = df[df["RAW MATERIAL"].isin(selected_m)]

# COLOR
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
# STATS
# =========================
g = df.groupby("Characteristic")

stats = pd.DataFrame({
    "Characteristic": g["Characteristic"].first(),
    "USL": g["USL"].first(),
    "LSL": g["LSL"].first(),
    "Mean": g["Value"].mean(),
    "Std": g["Value"].std(),
    "Max": g["Value"].max(),
    "Min": g["Value"].min(),
    "Count": g["Value"].count()
}).reset_index(drop=True)

stats["Std"] = stats["Std"].replace(0, np.nan)

# =========================
# METRICS
# =========================
stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Std"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Mean"]) / (3 * stats["Std"]),
    (stats["Mean"] - stats["LSL"]) / (3 * stats["Std"])
)

stats["Range"] = stats["Max"] - stats["Min"]

# =========================
# OOS
# =========================
above = df[df["Value"] > df["USL"]].groupby("Characteristic")["Value"].count()
below = df[df["Value"] < df["LSL"]].groupby("Characteristic")["Value"].count()

stats["Above OOS"] = stats["Characteristic"].map(above).fillna(0).astype(int)
stats["Below OOS"] = stats["Characteristic"].map(below).fillna(0).astype(int)

# =========================
# CAPABILITY TEXT
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
# PARETO
# =========================
pareto = stats[["Characteristic", "Above OOS", "Below OOS"]].copy()
pareto["Total OOS"] = pareto["Above OOS"] + pareto["Below OOS"]
pareto = pareto.sort_values("Total OOS", ascending=False)
pareto["Cum %"] = pareto["Total OOS"].cumsum() / pareto["Total OOS"].sum() * 100

# =========================
# STYLE TABLE
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
vals = data["Value"].dropna()
row = stats[stats["Characteristic"] == char].iloc[0]

# =========================
# SUMMARY
# =========================
st.subheader("Summary")

st.dataframe(pd.DataFrame({
    "Mean": [row["Mean"]],
    "Std": [row["Std"]],
    "Min": [row["Min"]],
    "Max": [row["Max"]],
    "Range": [row["Range"]],
    "Cp": [row["Cp"]],
    "Cpk": [row["Cpk"]],
    "Above OOS": [row["Above OOS"]],
    "Below OOS": [row["Below OOS"]],
    "Capability": [row["Capability"]],
}), use_container_width=True)

# =========================
# ROW 1: CONTROL + HISTOGRAM
# =========================
st.subheader("Distribution")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Control Chart")
    fig, ax = plt.subplots()
    ax.plot(vals.values, marker="o")
    ax.axhline(row["Mean"], color="green")
    ax.axhline(row["USL"], color="red")
    ax.axhline(row["LSL"], color="red")
    ax.grid()
    st.pyplot(fig)

with col2:
    st.markdown("### Histogram + Normal")
    fig, ax = plt.subplots()
    ax.hist(vals, bins=20, density=True, alpha=0.6)

    if len(vals) > 1:
        x = np.linspace(vals.min(), vals.max(), 100)
        y = norm.pdf(x, vals.mean(), vals.std())
        ax.plot(x, y, color="red")

    ax.grid()
    st.pyplot(fig)

# =========================
# ROW 2: MR + CAPABILITY
# =========================
st.subheader("Stability & Capability")

col3, col4 = st.columns(2)

with col3:
    st.markdown("### Moving Range")

    mr = vals.diff().abs().dropna()

    fig, ax = plt.subplots()
    ax.plot(mr.values, marker="o", color="orange")
    ax.axhline(mr.mean(), color="green")

    if len(mr) > 0:
        ax.axhline(mr.mean() * 3.267, color="red", linestyle="--")

    ax.grid()
    st.pyplot(fig)

with col4:
    st.markdown("### Capability (Cp / Cpk)")

    fig, ax = plt.subplots()
    ax.bar(["Cp", "Cpk"], [row["Cp"], row["Cpk"]])
    ax.axhline(1.33, color="red", linestyle="--")
    ax.axhline(1.0, color="orange", linestyle="--")
    ax.set_ylim(0, max(2, row["Cp"], row["Cpk"]))
    ax.grid()
    st.pyplot(fig)

# =========================
# BOXPLOT
# =========================
st.subheader("Boxplot per Characteristic")

fig, ax = plt.subplots(figsize=(10, 4))

box_data = [
    df[df["Characteristic"] == c]["Value"].dropna()
    for c in stats["Characteristic"]
]

ax.boxplot(box_data, labels=stats["Characteristic"], showfliers=True)
ax.tick_params(axis='x', rotation=90)
ax.grid()

st.pyplot(fig)

# =========================
# PARETO
# =========================
st.subheader("Pareto OOS")

fig, ax1 = plt.subplots()

ax1.bar(pareto["Characteristic"], pareto["Total OOS"])
ax1.set_ylabel("OOS")

ax2 = ax1.twinx()
ax2.plot(pareto["Characteristic"], pareto["Cum %"], color="red", marker="o")
ax2.set_ylabel("Cumulative %")

ax2.axhline(80, linestyle="--", color="gray")

plt.xticks(rotation=90)
plt.tight_layout()

st.pyplot(fig)
