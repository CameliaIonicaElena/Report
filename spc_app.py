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
st.sidebar.header("Filters")

# =========================
# DATE FILTER
# =========================
dates = df["DATE"].dropna().unique()
selected_date = st.sidebar.selectbox("DATE", sorted(dates))

df_filtered = df[df["DATE"] == selected_date]

# =========================
# RAW MATERIAL FILTER
# =========================
materials = df_filtered["RAW MATERIAL"].dropna().unique()
selected_material = st.sidebar.selectbox("RAW MATERIAL", sorted(materials))

df_filtered = df_filtered[df_filtered["RAW MATERIAL"] == selected_material]

# =========================
# COLOR FILTER
# =========================
colors = df_filtered["COLOR"].dropna().unique()
selected_color = st.sidebar.selectbox("COLOR", sorted(colors))

df_filtered = df_filtered[df_filtered["COLOR"] == selected_color]
# =========================
# SPEC LIMITS
# =========================
df["USL"] = df["Target"] + df["Upper Dev"]
df["LSL"] = df["Target"] + df["Lower Dev"]

# =========================
# GROUP STATS
# =========================
g = df.groupby("Characteristic")

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
# OUT OF SPEC COUNTS
# =========================
above = df[df["Value"] > df["USL"]].groupby("Characteristic")["Value"].count()
below = df[df["Value"] < df["LSL"]].groupby("Characteristic")["Value"].count()

stats["Above lower tolerance limit"] = stats["Characteristic"].map(above).fillna(0).astype(int)
stats["Below lower tolerance limit"] = stats["Characteristic"].map(below).fillna(0).astype(int)

# =========================
# CAPABILITY CLASS
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

# =========================
# TABLE DISPLAY
# =========================
st.subheader("SPC Summary")
st.dataframe(stats)

# =========================
# CHARACTERISTIC SELECTOR
# =========================
char = st.selectbox("Select Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]

# =========================
# LINE CHART (SPC)
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
