import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt

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
# EXTRA METRICS
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
# ABOVE / BELOW TOLERANCE
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
# FINAL ORDER
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
# STREAMLIT OUTPUT
# =========================
st.subheader("SPC Table")
st.dataframe(stats)

# =========================
# SELECT CHARACTERISTIC
# =========================
char = st.selectbox("Select Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]

# =========================
# PLOT (SINGLE + CLEAN)
# =========================
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
# MULTI-PLOT (SIXPACK STYLE)
# =========================
st.subheader("All Characteristics Overview")

selected = stats["Characteristic"].tolist()

for ch in selected:

    d = df[df["Characteristic"] == ch]
    s = stats[stats["Characteristic"] == ch].iloc[0]

    fig, ax = plt.subplots(figsize=(10, 3))

    ax.plot(d["Value"].values, marker="o", linewidth=1)

    ax.axhline(s["Xbar"], color="green")
    ax.axhline(s["USL"], color="red")
    ax.axhline(s["LSL"], color="red")

    ax.set_title(f"{ch} | Cp={s['Cp']:.2f} | Cpk={s['Cpk']:.2f}")
    ax.grid(True)

    st.pyplot(fig)

from scipy.stats import norm
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

st.subheader("Histogram + Normal Curve")

char = st.selectbox("Select Characteristic (Histogram)", df["Characteristic"].unique())

data = df[df["Characteristic"] == char]["Value"].dropna()

if len(data) > 1:

    mean = data.mean()
    std = data.std()

    fig, ax = plt.subplots(figsize=(10, 4))

    # =========================
    # HISTOGRAM
    # =========================
    ax.hist(data, bins=20, density=True, alpha=0.6, color="skyblue")

    # =========================
    # NORMAL CURVE
    # =========================
    x = np.linspace(data.min(), data.max(), 100)
    y = norm.pdf(x, mean, std)

    ax.plot(x, y, color="red", linewidth=2, label="Normal curve")

    # =========================
    # LINES
    # =========================
    ax.axvline(mean, color="green", linestyle="--", label="Mean")

    spec = stats[stats["Characteristic"] == char].iloc[0]

    ax.axvline(spec["USL"], color="red", linestyle="--", label="USL")
    ax.axvline(spec["LSL"], color="red", linestyle="--", label="LSL")

    ax.set_title(f"{char} | Histogram + Normal Curve")
    ax.legend()
    ax.grid(True)

    st.pyplot(fig)

else:
    st.warning("Not enough data for histogram")
