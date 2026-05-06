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

if st.sidebar.checkbox("Select all RAW MATERIAL", True):
    selected_m = materials
else:
    selected_m = st.sidebar.multiselect("RAW MATERIAL", materials, default=materials)

df = df[df["RAW MATERIAL"].isin(selected_m)]

if st.sidebar.checkbox("Select all COLOR", True):
    selected_c = colors
else:
    selected_c = st.sidebar.multiselect("COLOR", colors, default=colors)

df = df[df["COLOR"].isin(selected_c)]

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
    "Mean": g["Value"].mean(),
    "Std": g["Value"].std(),
    "Max": g["Value"].max(),
    "Min": g["Value"].min(),
    "Count": g["Value"].count()
}).reset_index(drop=True)

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
def style(df):
    s = pd.DataFrame("", index=df.index, columns=df.columns)
    s.loc[df["Above OOS"] > 0, "Above OOS"] = "color:red;font-weight:bold;text-decoration:underline"
    s.loc[df["Below OOS"] > 0, "Below OOS"] = "color:red;font-weight:bold;text-decoration:underline"
    return s

st.subheader("SPC Summary")
st.dataframe(stats.style.apply(style, axis=None), use_container_width=True)

# =========================
# MEASUREMENT POINT
# =========================
st.markdown("## Measurement point")

char = st.selectbox("Select measurement point", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

# =========================
# CHARACTERISTIC ANALYSIS
# =========================
st.markdown("## Characteristic analysis")

c1, c2 = st.columns(2)

with c1:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.plot(values.values, marker="o")
    ax.axhline(spec["Mean"], color="green")
    ax.axhline(spec["USL"], color="red")
    ax.axhline(spec["LSL"], color="red")

    ax.set_title("Control Chart")
    ax.grid()

    st.pyplot(fig)
    st.markdown("Legend: Mean / USL / LSL / Measurements")

with c2:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.hist(values, bins=20, density=True, alpha=0.6)

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        y = norm.pdf(x, values.mean(), values.std())
        ax.plot(x, y)

    ax.set_title("Histogram + Normal Curve")
    ax.grid()

    st.pyplot(fig)
    st.markdown("Legend: Distribution + Normal fit")

# =========================
# SECOND ROW
# =========================
c3, c4 = st.columns(2)

with c3:
    if len(values) > 1:
        mean = values.mean()
        mr = values.diff().abs().dropna()
        sigma = mr.mean() / 1.128

        UCL = mean + 3 * sigma
        LCL = mean - 3 * sigma

        fig, ax = plt.subplots(2, 1, figsize=(6, 4), sharex=True)

        ax[0].plot(values.values)
        ax[0].axhline(mean, color="green")
        ax[0].axhline(UCL, color="red", linestyle="--")
        ax[0].axhline(LCL, color="red", linestyle="--")
        ax[0].set_title("I Chart")
        ax[0].grid()

        ax[1].plot(mr.values, color="orange")
        ax[1].axhline(mr.mean(), color="green")
        ax[1].axhline(mr.mean()*3.267, color="red", linestyle="--")
        ax[1].set_title("Moving Range")
        ax[1].grid()

        st.pyplot(fig)
        st.markdown("Legend: variation + control limits")

with c4:
    fig, ax = plt.subplots()

    ax.bar(["Cp", "Cpk"], [spec["Cp"], spec["Cpk"]])
    ax.axhline(1.33, color="red", linestyle="--")

    ax.set_title("Capability")
    ax.grid()

    st.pyplot(fig)
    st.markdown(f"Legend: Cp={spec['Cp']:.2f}, Cpk={spec['Cpk']:.2f}")

# =========================
# GLOBAL OVERVIEW
# =========================
st.markdown("## General overview for selected closure")

c5, c6 = st.columns(2)

# BOX PLOT
with c5:
    fig, ax = plt.subplots(figsize=(6, 4))

    df.boxplot(column="Value", by="Characteristic", ax=ax, grid=False)

    ax.set_title("")
    ax.set_xlabel("")
    ax.set_ylabel("Value")
    plt.xticks(rotation=90)

    st.pyplot(fig)
    st.markdown("Legend: distribution per characteristic")

# PARETO (FIXED)
with c6:
    pareto = stats.copy()
    pareto["OOS"] = pareto["Above OOS"] + pareto["Below OOS"]
    pareto = pareto.sort_values("OOS", ascending=False)

    pareto["CumSum"] = pareto["OOS"].cumsum()
    pareto["CumPerc"] = 100 * pareto["CumSum"] / pareto["OOS"].sum()

    fig, ax1 = plt.subplots(figsize=(6, 4))

    # bars
    ax1.bar(pareto["Characteristic"], pareto["OOS"])
    ax1.set_ylabel("OOS Count")

    # line
    ax2 = ax1.twinx()
    ax2.plot(pareto["Characteristic"], pareto["CumPerc"], marker="o")
    ax2.set_ylabel("Cumulative %")

    # 80% threshold
    ax2.axhline(80, linestyle="--")

    plt.xticks(rotation=90)

    st.pyplot(fig)
    st.markdown("Legend: bars = OOS count | line = cumulative % | dashed = 80% threshold")
