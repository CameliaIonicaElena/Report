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
# BASE PATH (SharePoint sync local)
# =========================
BASE_PATH = r"C:\Users\RO10471\SIG\GQM Spouts - Documents\Measurements-test files"

# =========================
# SAFETY CHECK
# =========================
if not os.path.exists(BASE_PATH):
    st.error(f"Folder not found: {BASE_PATH}")
    st.stop()

files_list = [f for f in os.listdir(BASE_PATH) if f.endswith(".xlsx")]

if len(files_list) == 0:
    st.error("No Excel files found in folder")
    st.stop()

# =========================
# DATASET SELECTOR (DYNAMIC)
# =========================
selected_file = st.sidebar.selectbox("Select dataset", files_list)
file_path = os.path.join(BASE_PATH, selected_file)

# =========================
# LOAD DATA (SAFE)
# =========================
df_meas = pd.read_excel(file_path, sheet_name="Measurements")
df_specs = pd.read_excel(file_path, sheet_name="Specs")

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

df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")

df = df.dropna(subset=["Value", "DATE"])

# =========================
# FILTERS
# =========================
st.sidebar.header("Filters")

min_date, max_date = df["DATE"].min(), df["DATE"].max()

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

df = df[(df["DATE"] >= pd.to_datetime(start_date)) &
        (df["DATE"] <= pd.to_datetime(end_date))]

# RAW MATERIAL
materials = sorted(df["RAW MATERIAL"].dropna().unique())
select_all_m = st.sidebar.checkbox("Select all RAW MATERIAL", value=True)

selected_materials = materials if select_all_m else st.sidebar.multiselect(
    "RAW MATERIAL", materials
)

if selected_materials:
    df = df[df["RAW MATERIAL"].isin(selected_materials)]

# COLOR
colors = sorted(df["COLOR"].dropna().unique())
select_all_c = st.sidebar.checkbox("Select all COLOR", value=True)

selected_colors = colors if select_all_c else st.sidebar.multiselect(
    "COLOR", colors
)

if selected_colors:
    df = df[df["COLOR"].isin(selected_colors)]

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
above = df[df["Value"] > df["USL"]].groupby("Characteristic")["Value"].count()
below = df[df["Value"] < df["LSL"]].groupby("Characteristic")["Value"].count()

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
# STYLE OOS (RED + BOLD)
# =========================
def style(df):
    s = pd.DataFrame("", index=df.index, columns=df.columns)
    s.loc[df["Above OOS"] > 0, "Above OOS"] = "color:red;font-weight:bold"
    s.loc[df["Below OOS"] > 0, "Below OOS"] = "color:red;font-weight:bold"
    return s

st.subheader("SPC Summary")
st.dataframe(stats.style.apply(style, axis=None), use_container_width=True)

# =========================
# CHARACTERISTIC SELECTOR
# =========================
char = st.selectbox("Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]

values = data["Value"].dropna()

# =========================
# CHARTS LAYOUT
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
