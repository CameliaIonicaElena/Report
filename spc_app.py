import streamlit as st
import pandas as pd
import plotly.express as px

st.title("SPC Dashboard")

# LOAD DIN ACELASI EXCEL (2 sheet-uri)
file = "Test-Measurements&Specs.xlsx"

df_meas = pd.read_excel(file, sheet_name="Measurements")
df_specs = pd.read_excel(file, sheet_name="Specs")

# TRANSFORM (UNPIVOT)
df_long = df_meas.melt(
    id_vars=["Date", "Material", "Color"],
    var_name="Characteristic",
    value_name="Value"
)

# MERGE
df = df_long.merge(df_specs, on="Characteristic", how="left")

# SELECT
char = st.selectbox("Choose characteristic", df["Characteristic"].unique())

data = df[df["Characteristic"] == char].dropna()

# GRAFIC
fig = px.line(data, y="Value", title=char)

st.plotly_chart(fig)
