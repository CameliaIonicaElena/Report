import requests
from io import BytesIO
import pandas as pd
import streamlit as st

@st.cache_data(ttl=600)
def load_data(url):
    response = requests.get(url)
    
    if response.status_code != 200:
        raise Exception("Failed to load file from SharePoint")

    xls = pd.ExcelFile(BytesIO(response.content))

    df_meas = xls.parse("Measurements")
    df_specs = xls.parse("Specs")

    df_meas.columns = df_meas.columns.str.strip()
    df_specs.columns = df_specs.columns.str.strip()

    return df_meas, df_specs
# ==============================
# 🎯 SELECT FILE
# ==============================
selected_file = st.selectbox("Select dataset", list(files.keys()))

df_meas, df_specs = load_data(files[selected_file])

# ==============================
# 🔄 REFRESH BUTTON
# ==============================
if st.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()

# ==============================
# 🔧 UNPIVOT MEASUREMENTS
# ==============================
id_vars = ["Date", "RAW MATERIAL", "COLOR"]

df_long = df_meas.melt(
    id_vars=id_vars,
    var_name="Characteristic",
    value_name="Value"
)

# ==============================
# 🔗 MERGE WITH SPECS
# ==============================
df = df_long.merge(df_specs, on="Characteristic", how="left")

# ==============================
# 🎯 FILTERS
# ==============================
st.sidebar.header("Filters")

materials = sorted(df["RAW MATERIAL"].dropna().unique())
selected_material = st.sidebar.selectbox("Raw Material", ["All"] + materials)

colors = sorted(df["COLOR"].dropna().unique())
selected_color = st.sidebar.selectbox("Color", ["All"] + colors)

chars = sorted(df["Characteristic"].dropna().unique())
selected_char = st.sidebar.selectbox("Characteristic", ["All"] + chars)

# ==============================
# 🧹 APPLY FILTERS
# ==============================
df_filtered = df.copy()

if selected_material != "All":
    df_filtered = df_filtered[df_filtered["RAW MATERIAL"] == selected_material]

if selected_color != "All":
    df_filtered = df_filtered[df_filtered["COLOR"] == selected_color]

if selected_char != "All":
    df_filtered = df_filtered[df_filtered["Characteristic"] == selected_char]

# ==============================
# 📊 KPI CALCULATIONS
# ==============================
df_filtered["Value"] = pd.to_numeric(df_filtered["Value"], errors="coerce")

mean_val = df_filtered["Value"].mean()
std_val = df_filtered["Value"].std()

# dacă ai USL / LSL în Specs
if "USL" in df_filtered.columns and "LSL" in df_filtered.columns:
    df_filtered["USL"] = pd.to_numeric(df_filtered["USL"], errors="coerce")
    df_filtered["LSL"] = pd.to_numeric(df_filtered["LSL"], errors="coerce")

    cp = (df_filtered["USL"].iloc[0] - df_filtered["LSL"].iloc[0]) / (6 * std_val) if std_val != 0 else None
else:
    cp = None

# ==============================
# 📊 DISPLAY
# ==============================
st.title("📊 SPC Dashboard")

col1, col2, col3 = st.columns(3)

col1.metric("Mean", round(mean_val, 3) if pd.notnull(mean_val) else "-")
col2.metric("Std Dev", round(std_val, 3) if pd.notnull(std_val) else "-")
col3.metric("Cp", round(cp, 3) if cp else "-")

st.dataframe(df_filtered)

# ==============================
# 📈 CHART
# ==============================
st.line_chart(df_filtered.set_index("Date")["Value"])
