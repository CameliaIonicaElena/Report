import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

# =========================
# STREAMLIT CONFIG (MUST BE FIRST)
# =========================
st.set_page_config(layout="wide")

# =========================
# TITLE
# =========================
st.title("SPC Dashboard")

# =========================
# LOAD DATA
# =========================
file = "Test-Measurements&Specs.xlsx"

df_meas = pd.read_excel(file, sheet_name="Measurements")
df_specs = pd.read_excel(file, sheet_name="Specs")

df_meas.columns = df_meas.columns.str.strip()
df_specs.columns = df_specs.columns.str.strip()

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

min_date = df["DATE"].min()
max_date = df["DATE"].max()

start_date, end_date = st.sidebar.date_input(
    "DATE range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

df_filtered = df[
    (df["DATE"] >= pd.to_datetime(start_date)) &
    (df["DATE"] <= pd.to_datetime(end_date))
]

# RAW MATERIAL
materials = sorted(df_filtered["RAW MATERIAL"].dropna().unique())
select_all_m = st.sidebar.checkbox("Select all RAW MATERIAL", value=True)

selected_materials = materials if select_all_m else st.sidebar.multiselect(
    "RAW MATERIAL", materials
)

if len(selected_materials) > 0:
    df_filtered = df_filtered[df_filtered["RAW MATERIAL"].isin(selected_materials)]

# COLOR
colors = sorted(df_filtered["COLOR"].dropna().unique())
select_all_c = st.sidebar.checkbox("Select all COLOR", value=True)

selected_colors = colors if select_all_c else st.sidebar.multiselect(
    "COLOR", colors
)

if len(selected_colors) > 0:
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
# OUT OF SPEC
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
# TABLE STYLE (🔥 FIX REQUESTED)
# =========================
def highlight_oos(df):
    style = pd.DataFrame("", index=df.index, columns=df.columns)

    style.loc[df["Above OOS"] > 0, "Above OOS"] = "color: red; font-weight: bold"
    style.loc[df["Below OOS"] > 0, "Below OOS"] = "color: red; font-weight: bold"

    return style

st.subheader("SPC Summary")
st.dataframe(
    stats.style.apply(highlight_oos, axis=None),
    use_container_width=True
)

# =========================
# CHARACTERISTIC
# =========================
char = st.selectbox("Select Characteristic", stats["Characteristic"])

data = df_filtered[df_filtered["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]

values = data["Value"].dropna()

# =========================
# LAYOUT
# =========================
st.subheader("Charts")

col1, col2 = st.columns(2)

# CONTROL CHART
with col1:
    fig, ax = plt.subplots()

    ax.plot(values.values, marker="o", linewidth=1)
    ax.axhline(spec["Xbar"], color="green")
    ax.axhline(spec["USL"], color="red")
    ax.axhline(spec["LSL"], color="red")

    ax.set_title("Control Chart")
    ax.grid(True)

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
    ax2.grid(True)

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

    fig, ax = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

    ax[0].plot(values.values, marker="o")
    ax[0].axhline(mean, color="green")
    ax[0].axhline(UCL, color="red", linestyle="--")
    ax[0].axhline(LCL, color="red", linestyle="--")
    ax[0].set_title("I Chart")
    ax[0].grid()

    MR_UCL = mr.mean() * 3.267

    ax[1].plot(mr.values, marker="o", color="orange")
    ax[1].axhline(mr.mean(), color="green")
    ax[1].axhline(MR_UCL, color="red", linestyle="--")
    ax[1].set_title("MR Chart")
    ax[1].grid()

    st.pyplot(fig)

else:
    st.warning("Not enough data")
