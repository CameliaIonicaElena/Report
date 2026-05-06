import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")

# SIG-like palette (soft industrial)
COLOR_PRIMARY = "#1f4e79"
COLOR_RED = "#c00000"
COLOR_GREEN = "#2e7d32"
COLOR_GREY = "#666666"

st.title("SPC Dashboard")

# =========================
# LOAD DATA
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

df_meas["DATE"] = pd.to_datetime(df_meas["DATE"])

# =========================
# TRANSFORM
# =========================
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

min_d, max_d = df["DATE"].min(), df["DATE"].max()

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(min_d, max_d),
    min_value=min_d,
    max_value=max_d
)

df = df[(df["DATE"] >= pd.to_datetime(start_date)) &
        (df["DATE"] <= pd.to_datetime(end_date))]

materials = sorted(df["RAW MATERIAL"].dropna().unique())
colors = sorted(df["COLOR"].dropna().unique())

mat_all = st.sidebar.checkbox("Select all RAW MATERIAL", True)
col_all = st.sidebar.checkbox("Select all COLOR", True)

if mat_all:
    mat_sel = materials
else:
    mat_sel = st.sidebar.multiselect("RAW MATERIAL", materials)

if col_all:
    col_sel = colors
else:
    col_sel = st.sidebar.multiselect("COLOR", colors)

df = df[df["RAW MATERIAL"].isin(mat_sel)]
df = df[df["COLOR"].isin(col_sel)]

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

stats["Range"] = stats["Max"] - stats["Min"]

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Std"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Mean"]) / (3 * stats["Std"]),
    (stats["Mean"] - stats["LSL"]) / (3 * stats["Std"])
)

above = df[df["Value"] > df["USL"]].groupby("Characteristic")["Value"].count()
below = df[df["Value"] < df["LSL"]].groupby("Characteristic")["Value"].count()

stats["Above OOS"] = stats["Characteristic"].map(above).fillna(0).astype(int)
stats["Below OOS"] = stats["Characteristic"].map(below).fillna(0).astype(int)

# =========================
# STYLE TABLE
# =========================
def style_oos(df):
    style = pd.DataFrame("", index=df.index, columns=df.columns)

    for col in ["Above OOS", "Below OOS"]:
        style.loc[df[col] > 0, col] = (
            "color:red; font-weight:bold; text-decoration: underline"
        )

    return style

# =========================
# OVERVIEW TITLE
# =========================
st.markdown("## Characteristic Analysis")

st.dataframe(
    stats.style.apply(style_oos, axis=None),
    use_container_width=True
)

# =========================
# SELECT CHARACTERISTIC
# =========================
st.markdown("### Measurement point")

char = st.selectbox("Select Measurement point", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

# =========================
# CHARACTERISTIC ANALYSIS CHARTS
# =========================
st.markdown("## Characteristic Analysis")

c1, c2 = st.columns(2)

# CONTROL CHART
with c1:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.plot(values.values, marker="o", linewidth=1, color=COLOR_PRIMARY)
    ax.axhline(spec["Mean"], color=COLOR_GREEN)
    ax.axhline(spec["USL"], color=COLOR_RED)
    ax.axhline(spec["LSL"], color=COLOR_RED)

    ax.set_title("Control Chart")
    ax.grid()

    st.pyplot(fig)
    st.caption(f"Mean={spec['Mean']:.2f} | USL={spec['USL']:.2f} | LSL={spec['LSL']:.2f}")

# HISTOGRAM
with c2:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.hist(values, bins=20, density=True, alpha=0.6, color="#8aa6c1")

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        y = norm.pdf(x, values.mean(), values.std())
        ax.plot(x, y, color=COLOR_PRIMARY)

    ax.set_title("Histogram + Normal Curve")
    ax.grid()

    st.pyplot(fig)
    st.caption("Distribution + fitted normal curve")

# =========================
# SECOND ROW (I-MR + CAPABILITY)
# =========================
c3, c4 = st.columns(2)

# I-MR
with c3:
    if len(values) > 1:

        mean = values.mean()
        mr = values.diff().abs().dropna()
        sigma = mr.mean() / 1.128

        UCL = mean + 3 * sigma
        LCL = mean - 3 * sigma

        fig, ax = plt.subplots(2, 1, figsize=(6, 4), sharex=True)

        ax[0].plot(values.values, color=COLOR_PRIMARY)
        ax[0].axhline(mean, color=COLOR_GREEN)
        ax[0].axhline(UCL, color=COLOR_RED, linestyle="--")
        ax[0].axhline(LCL, color=COLOR_RED, linestyle="--")
        ax[0].set_title("I Chart")
        ax[0].grid()

        ax[1].plot(mr.values, color="orange")
        ax[1].axhline(mr.mean(), color=COLOR_GREEN)
        ax[1].axhline(mr.mean()*3.267, color=COLOR_RED, linestyle="--")
        ax[1].set_title("Moving Range")
        ax[1].grid()

        plt.tight_layout()
        st.pyplot(fig)

        st.caption("I-MR control logic (variation monitoring)")

# CAPABILITY
with c4:
    fig, ax = plt.subplots()

    ax.bar(["Cp", "Cpk"], [spec["Cp"], spec["Cpk"]], color=[COLOR_PRIMARY, COLOR_GREEN])
    ax.axhline(1.33, color=COLOR_RED, linestyle="--")

    ax.set_title("Capability")
    ax.grid()

    st.pyplot(fig)

    st.caption(f"Cp={spec['Cp']:.2f} | Cpk={spec['Cpk']:.2f}")

# =========================
# GLOBAL OVERVIEW
# =========================
st.markdown("## General overview for Selected Closure")

c5, c6 = st.columns(2)

# BOXPLOT
with c5:
    fig, ax = plt.subplots(figsize=(6, 4))

    df.boxplot(column="Value", by="Characteristic", ax=ax)
    plt.xticks(rotation=90)
    ax.set_title("Boxplot per Characteristic")
    ax.grid()

    st.pyplot(fig)

    st.caption("Distribution spread per characteristic")

# PARETO OOS
with c6:
    pareto = stats.copy()
    pareto["Total OOS"] = pareto["Above OOS"] + pareto["Below OOS"]
    pareto = pareto.sort_values("Total OOS", ascending=False)

    fig, ax = plt.subplots(figsize=(6, 4))

    ax.bar(pareto["Characteristic"], pareto["Total OOS"], color=COLOR_PRIMARY)
    plt.xticks(rotation=90)

    ax.set_title("Pareto OOS")
    ax.grid()

    st.pyplot(fig)

    st.caption("Defect prioritization (80/20 principle)")
