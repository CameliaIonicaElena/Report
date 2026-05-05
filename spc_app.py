import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

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

# =========================
# FILTERS (IMPORTANT FIX)
# =========================
st.sidebar.header("Filters")

# DATE RANGE
df["DATE"] = pd.to_datetime(df["DATE"])

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

select_all_materials = st.sidebar.checkbox("Select all RAW MATERIAL", value=True)

if select_all_materials:
    selected_materials = materials
else:
    selected_materials = st.sidebar.multiselect(
        "RAW MATERIAL",
        materials,
        default=[]
    )

df_filtered = df_filtered[df_filtered["RAW MATERIAL"].isin(selected_materials)]
colors = sorted(df_filtered["COLOR"].dropna().unique())

select_all_colors = st.sidebar.checkbox("Select all COLOR", value=True)

if select_all_colors:
    selected_colors = colors
else:
    selected_colors = st.sidebar.multiselect(
        "COLOR",
        colors,
        default=[]
    )

df_filtered = df_filtered[df_filtered["COLOR"].isin(selected_colors)]
# =========================
# SPEC LIMITS (IMPORTANT FIX → USE df_filtered)
# =========================
df_filtered["USL"] = df_filtered["Target"] + df_filtered["Upper Dev"]
df_filtered["LSL"] = df_filtered["Target"] + df_filtered["Lower Dev"]

# =========================
# GROUP STATS
# =========================
g = df_filtered.groupby("Characteristic")

stats = pd.DataFrame({
    "Characteristic": g["Characteristic"].first(),
    "Upper Dev": g["Upper Dev"].first(),
    "Lower Dev": g["Lower Dev"].first(),
    "USL": g["USL"].first(),
    "LSL": g["LSL"].first(),
    "Xbar": g["Value"].mean(),
    "Standard deviation": g["Value"].std(),
    "Max": g["Value"].max(),
    "Min": g["Value"].min(),
    "Count measured values": g["Value"].count()
}).reset_index(drop=True)

# =========================
# DERIVED METRICS
# =========================
stats["Range"] = stats["Max"] - stats["Min"]
stats["+3s"] = stats["Xbar"] + 3 * stats["Standard deviation"]
stats["-3s"] = stats["Xbar"] - 3 * stats["Standard deviation"]

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Standard deviation"])

stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Xbar"]) / (3 * stats["Standard deviation"]),
    (stats["Xbar"] - stats["LSL"]) / (3 * stats["Standard deviation"])
)

# =========================
# OUT OF SPEC
# =========================
above = df_filtered[df_filtered["Value"] > df_filtered["USL"]].groupby("Characteristic")["Value"].count()
below = df_filtered[df_filtered["Value"] < df_filtered["LSL"]].groupby("Characteristic")["Value"].count()

stats["Above lower tolerance limit"] = stats["Characteristic"].map(above).fillna(0).astype(int)
stats["Below lower tolerance limit"] = stats["Characteristic"].map(below).fillna(0).astype(int)

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
    else:
        return "Not capable"

stats["Process capability"] = stats["Cpk"].apply(capability)
stats["Bi Process capability"] = np.where(stats["Cpk"] >= 1.33, "YES", "NO")

# =========================
# FINAL TABLE
# =========================
stats = stats[
    [
        "Characteristic",
        "Upper Dev",
        "Lower Dev",
        "USL",
        "LSL",
        "Xbar",
        "Standard deviation",
        "Max",
        "Min",
        "Range",
        "Above lower tolerance limit",
        "Below lower tolerance limit",
        "+3s",
        "-3s",
        "Cp",
        "Cpk",
        "Process capability",
        "Bi Process capability",
        "Count measured values"
    ]
]

st.subheader("SPC Summary")
st.dataframe(stats)

# =========================
# CHARACTERISTIC SELECTOR
# =========================
char = st.selectbox("Select Characteristic", stats["Characteristic"])

data = df_filtered[df_filtered["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]

# =========================
# CONTROL CHART
# =========================
st.subheader("Control Chart")

fig, ax = plt.subplots(figsize=(10, 4))

ax.plot(data["Value"].values, marker="o", linewidth=1, label="Measurements")

ax.axhline(spec["Xbar"], color="green", label=f"Mean {spec['Xbar']:.3f}")
ax.axhline(spec["USL"], color="red", label=f"USL {spec['USL']:.3f}")
ax.axhline(spec["LSL"], color="red", label=f"LSL {spec['LSL']:.3f}")

ax.set_title(f"{char} | Cp={spec['Cp']:.2f} | Cpk={spec['Cpk']:.2f}")
ax.legend()
ax.grid(True)

st.pyplot(fig)

# =========================
# HISTOGRAM + NORMAL CURVE
# =========================
st.subheader("Histogram + Normal Curve")

values = data["Value"].dropna()

if len(values) > 1:

    mean = values.mean()
    std = values.std()

    fig2, ax2 = plt.subplots(figsize=(10, 4))

    ax2.hist(values, bins=20, density=True, alpha=0.6, color="skyblue")

    x = np.linspace(values.min(), values.max(), 100)
    y = norm.pdf(x, mean, std)

    ax2.plot(x, y, color="red", linewidth=2, label="Normal curve")

    ax2.axvline(mean, color="green", linestyle="--", label="Mean")
    ax2.axvline(spec["USL"], color="red", linestyle="--", label="USL")
    ax2.axvline(spec["LSL"], color="red", linestyle="--", label="LSL")

    ax2.set_title(f"{char} Distribution")
    ax2.legend()
    ax2.grid(True)

    st.pyplot(fig2)

else:
    st.warning("Not enough data for histogram")

st.subheader("I-MR Control Chart")

values = data["Value"].dropna().reset_index(drop=True)

if len(values) > 1:

    # =========================
    # INDIVIDUALS
    # =========================
    mean = values.mean()
    mr = values.diff().abs().dropna()

    mr_mean = mr.mean()

    # constants for I-MR
    d2 = 1.128  # for MR of 2

    sigma = mr_mean / d2

    UCL = mean + 3 * sigma
    LCL = mean - 3 * sigma

    # =========================
    # PLOT
    # =========================
    fig, ax = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

    # ---- Individuals chart ----
    ax[0].plot(values.values, marker="o", linewidth=1)
    ax[0].axhline(mean, color="green", label="Mean")
    ax[0].axhline(UCL, color="red", linestyle="--", label="UCL")
    ax[0].axhline(LCL, color="red", linestyle="--", label="LCL")

    ax[0].set_title(f"I Chart - {char}")
    ax[0].legend()
    ax[0].grid(True)

    # ---- Moving Range chart ----
    ax[1].plot(mr.values, marker="o", linewidth=1, color="orange")

    MR_UCL = mr_mean * 3.267  # standard constant for MR(2)

    ax[1].axhline(mr_mean, color="green", label="MR Mean")
    ax[1].axhline(MR_UCL, color="red", linestyle="--", label="UCL")

    ax[1].set_title("Moving Range Chart")
    ax[1].legend()
    ax[1].grid(True)

    plt.tight_layout()
    st.pyplot(fig)

else:
    st.warning("Not enough data for I-MR chart")
