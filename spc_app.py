import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from msal import ConfidentialClientApplication
import requests
from io import BytesIO
import urllib.parse

# =========================
# APP CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("📊 SPC Dashboard")

# =========================
# AUTH
# =========================
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
TENANT_ID = st.secrets["TENANT_ID"]
SITE_ID = st.secrets["SITE_ID"]

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

token = app.acquire_token_for_client(scopes=SCOPES)

if "access_token" not in token:
    st.error("❌ Azure authentication failed")
    st.stop()

headers = {"Authorization": f"Bearer {token['access_token']}"}

# =========================
# FILES (GRAPH)
# =========================
base_path = "Shared Documents/Measurements-test files"

def graph_url(file):
    return (
        f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drive/root:"
        f"/{urllib.parse.quote(base_path)}/{urllib.parse.quote(file)}:/content"
    )

files = {
    "Dataset 0": graph_url("Test-Measurements&Specs.xlsx"),
    "Dataset 1": graph_url("Test-Measurements&Specs1.xlsx"),
    "Dataset 2": graph_url("Test-Measurements&Specs2.xlsx"),
}

selected = st.sidebar.selectbox("Select dataset", list(files.keys()))
url = files[selected]

# =========================
# DOWNLOAD
# =========================
res = requests.get(url, headers=headers)

if res.status_code != 200:
    st.error("❌ Failed loading SharePoint file")
    st.write(res.text)
    st.stop()

excel = BytesIO(res.content)

# =========================
# LOAD DATA
# =========================
df_meas = pd.read_excel(excel, sheet_name="Measurements")
excel.seek(0)
df_specs = pd.read_excel(excel, sheet_name="Specs")

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
# FILTERS (MODERN UI)
# =========================
st.sidebar.header("🎛️ Filters")

min_d, max_d = df["DATE"].min(), df["DATE"].max()

start, end = st.sidebar.date_input(
    "Date range",
    value=(min_d, max_d),
    min_value=min_d,
    max_value=max_d
)

df = df[(df["DATE"] >= pd.to_datetime(start)) &
        (df["DATE"] <= pd.to_datetime(end))]

materials = sorted(df["RAW MATERIAL"].dropna().unique())
colors = sorted(df["COLOR"].dropna().unique())

col1, col2 = st.sidebar.columns(2)

with col1:
    if st.checkbox("All RM", True):
        selected_m = materials
    else:
        selected_m = st.multiselect("Raw Material", materials, default=materials)

with col2:
    if st.checkbox("All COLOR", True):
        selected_c = colors
    else:
        selected_c = st.multiselect("Color", colors, default=colors)

df = df[
    df["RAW MATERIAL"].isin(selected_m) &
    df["COLOR"].isin(selected_c)
]

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

stats["Std"] = stats["Std"].replace(0, np.nan)

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Std"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Mean"]) / (3 * stats["Std"]),
    (stats["Mean"] - stats["LSL"]) / (3 * stats["Std"])
)

# =========================
# TABLE
# =========================
st.subheader("📋 SPC Summary")
st.dataframe(stats, use_container_width=True, height=350)

# =========================
# SELECT CHARACTERISTIC
# =========================
st.markdown("## 📌 Measurement Point")

char = st.selectbox("Select characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

# =========================
# ROW 1 - CONTROL + HISTOGRAM
# =========================
c1, c2 = st.columns(2)

with c1:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.plot(values.values, marker="o", color="#1f77b4", linewidth=1.5, label="Values")
    ax.axhline(spec["Mean"], color="green", linewidth=2, label="Mean")
    ax.axhline(spec["USL"], color="red", linestyle="--", linewidth=2, label="USL")
    ax.axhline(spec["LSL"], color="orange", linestyle="--", linewidth=2, label="LSL")

    ax.set_title("Control Chart", fontweight="bold")
    ax.grid(alpha=0.3)
    ax.legend()

    st.pyplot(fig)

with c2:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.hist(values, bins=20, density=True, alpha=0.6,
            color="#6BAED6", edgecolor="black")

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        ax.plot(x, norm.pdf(x, values.mean(), values.std()),
                color="purple", linewidth=2)

    ax.set_title("Histogram + Normal Curve", fontweight="bold")
    ax.grid(alpha=0.3)

    st.pyplot(fig)

# =========================
# ROW 2 - CAPABILITY
# =========================
st.subheader("📐 Capability")

fig, ax = plt.subplots(figsize=(5, 3))

ax.bar(["Cp", "Cpk"],
       [spec["Cp"], spec["Cpk"]],
       color=["#1f77b4", "#17becf"])

ax.axhline(1.33, color="red", linestyle="--", linewidth=2)
ax.set_title("Process Capability", fontweight="bold")
ax.grid(alpha=0.3)

st.pyplot(fig)
