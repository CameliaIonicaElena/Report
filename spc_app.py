import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.title("SPC Dashboard")

# LOAD
file = "Test-Measurements&Specs.xlsx"

df_meas = pd.read_excel(file, sheet_name="Measurements")
df_specs = pd.read_excel(file, sheet_name="Specs")

# CLEAN
df_meas.columns = df_meas.columns.str.strip()
df_specs.columns = df_specs.columns.str.strip()

# TRANSFORM
df_long = df_meas.melt(
    id_vars=["Date", "Material", "Color"],
    var_name="Characteristic",
    value_name="Value"
)

df = df_long.merge(df_specs, on="Characteristic", how="left")

# 🔥 SELECTOR (IMPORTANT)
char = st.selectbox("Choose characteristic", df["Characteristic"].unique())

data = df[df["Characteristic"] == char].dropna()

# 🔥 AICI VINE CODUL TĂU DIN JUPYTER

mean = data["Value"].mean()
std = data["Value"].std()

USL = data["USL"].iloc[0]
LSL = data["LSL"].iloc[0]

Cp = (USL - LSL) / (6 * std)
Cpk = min((USL - mean) / (3 * std), (mean - LSL) / (3 * std))

# 🔥 AFIȘARE
st.write(f"Mean: {mean}")
st.write(f"Std: {std}")
st.write(f"Cp: {Cp}")
st.write(f"Cpk: {Cpk}")

# 🔥 GRAFIC (ca în Jupyter)
fig, ax = plt.subplots()
ax.plot(data["Value"], marker='o')
ax.axhline(mean, linestyle='--', label="Mean")
ax.axhline(USL, color='r', label="USL")
ax.axhline(LSL, color='r', label="LSL")

ax.legend()
ax.set_title(char)

st.pyplot(fig)
