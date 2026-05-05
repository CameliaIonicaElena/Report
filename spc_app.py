import streamlit as st
import pandas as pd
import numpy as np

st.title("SPC Dashboard")

# 🔹 FILE (IMPORTANT - fara path local!)
file = "Test-Measurements&Specs.xlsx"

# 🔹 LOAD
df_specs = pd.read_excel(file, sheet_name="Specs")
df_meas = pd.read_excel(file, sheet_name="Measurements")

# 🔹 CLEAN COLUMNS
df_meas.columns = df_meas.columns.str.strip()
df_specs.columns = df_specs.columns.str.strip()

# 🔹 UNPIVOT
df_long = df_meas.melt(
    id_vars=["DATE", "RAW MATERIAL", "COLOR", "CAV"],
    var_name="Characteristic",
    value_name="Value"
)

# 🔹 MERGE
df = df_long.merge(df_specs, on="Characteristic", how="left")

# 🔹 LIMITS
df["USL"] = df["Target"] + df["Upper Dev"]
df["LSL"] = df["Target"] + df["Lower Dev"]

# 🔹 GROUP
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

# 🔹 EXTRA CALC
stats["Range"] = stats["Max"] - stats["Min"]
stats["+3s"] = stats["Xbar"] + 3 * stats["Standard deviation"]
stats["-3s"] = stats["Xbar"] - 3 * stats["Standard deviation"]

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Standard deviation"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Xbar"]) / (3 * stats["Standard deviation"]),
    (stats["Xbar"] - stats["LSL"]) / (3 * stats["Standard deviation"])
)

# 🔹 OUT OF SPEC
above = df[df["Value"] > df["USL"]].groupby("Characteristic")["Value"].count()
below = df[df["Value"] < df["LSL"]].groupby("Characteristic")["Value"].count()

stats["Above lower tolerance limit"] = stats["Characteristic"].map(above).fillna(0).astype(int)
stats["Below lower tolerance limit"] = stats["Characteristic"].map(below).fillna(0).astype(int)

# 🔹 CAPABILITY
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

# 🔹 ORDER COLUMNS
stats = stats[
    [
        "Characteristic", "Upper Dev", "Lower Dev", "USL", "LSL",
        "Xbar", "Standard deviation", "Max", "Min", "Range",
        "Above lower tolerance limit", "Below lower tolerance limit",
        "+3s", "-3s", "Cp", "Cpk",
        "Process capability", "Bi Process capability",
        "Count measured values"
    ]
]

# 🔹 COLORING
def highlight(row):
    color = []
    for col in row.index:
        if col in ["Above lower tolerance limit", "Below lower tolerance limit"] and row[col] > 0:
            color.append("background-color: #ffcccc")
        else:
            color.append("")
    return color

styled_stats = stats.style.apply(highlight, axis=1)

# 🔹 DISPLAY

st.subheader("SPC Summary Table")
st.dataframe(stats)

# 🔹 OPTIONAL FILTER
char = st.selectbox("Select Characteristic", stats["Characteristic"])

filtered = df[df["Characteristic"] == char]

st.subheader(f"Details for {char}")
st.dataframe(filtered)
