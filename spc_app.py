import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from msal import ConfidentialClientApplication
import requests
from io import BytesIO

# =========================
# APP CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("SPC Dashboard")

# =========================
# AZURE SECRETS
# =========================
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
TENANT_ID = st.secrets["TENANT_ID"]

SITE_ID = "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Hefei:"

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

# =========================
# AUTH
# =========================
app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

token = app.acquire_token_for_client(scopes=SCOPES)

if "access_token" not in token:
    st.error("Azure authentication failed")
    st.write(token)
    st.stop()

headers = {"Authorization": f"Bearer {token['access_token']}"}

# =========================
# GET DRIVE
# =========================
@st.cache_data
def get_drive():
    url = f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drives"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Failed to fetch drives")
        st.write(res.text)
        st.stop()

    return res.json()["value"][0]

drive = get_drive()
DRIVE_ID = drive["id"]

st.sidebar.success(f"Drive: {drive['name']}")

# =========================
# LIST FILES (SAFE METHOD)
# =========================
@st.cache_data
def list_files():
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root/children"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Failed to list files")
        st.write(res.text)
        st.stop()

    return res.json()["value"]

files_in_drive = list_files()

# =========================
# GET FILE ID (EXACT MATCH)
# =========================
def get_file_id(file_name):
    for f in files_in_drive:
        if f["name"] == file_name:
            return f["id"]

    st.error(f"File not found: {file_name}")
    st.write("Available files:")
    st.write([f["name"] for f in files_in_drive])
    st.stop()

# =========================
# DOWNLOAD FILE
# =========================
def download_file(file_id):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{file_id}/content"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Failed to download file")
        st.write(res.text)
        st.stop()

    return BytesIO(res.content)

# =========================
# FILE SELECTION
# =========================
files = {
    "Dataset 0": "Test-Measurements&Specs.xlsx",
    "Dataset 1": "Test-Measurements&Specs1.xlsx",
    "Dataset 2": "Test-Measurements&Specs2.xlsx",
}

selected = st.sidebar.selectbox("Select dataset", list(files.keys()))
file_name = files[selected]

file_id = get_file_id(file_name)
excel = download_file(file_id)

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
# FILTERS
# =========================
st.sidebar.header("Filters")

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(df["DATE"].min(), df["DATE"].max())
)

df = df[(df["DATE"] >= pd.to_datetime(start_date)) &
        (df["DATE"] <= pd.to_datetime(end_date))]

materials = sorted(df["RAW MATERIAL"].dropna().unique())
colors = sorted(df["COLOR"].dropna().unique())

selected_m = st.sidebar.multiselect("RAW MATERIAL", materials, default=materials)
selected_c = st.sidebar.multiselect("COLOR", colors, default=colors)

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

st.subheader("SPC Summary")
st.dataframe(stats, use_container_width=True)

# =========================
# CHARTS
# =========================
char = st.selectbox("Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

c1, c2 = st.columns(2)

with c1:
    fig, ax = plt.subplots()
    ax.plot(values.values, marker="o")
    ax.axhline(spec["Mean"])
    ax.axhline(spec["USL"], linestyle="--")
    ax.axhline(spec["LSL"], linestyle="--")
    ax.set_title("Control Chart")
    st.pyplot(fig)

with c2:
    fig, ax = plt.subplots()
    ax.hist(values, bins=20, density=True, alpha=0.6)

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        ax.plot(x, norm.pdf(x, values.mean(), values.std()))

    ax.set_title("Histogram")
    st.pyplot(fig)

# =========================
# CAPABILITY
# =========================
st.subheader("Capability")

fig, ax = plt.subplots()
ax.bar(["Cp", "Cpk"], [spec["Cp"], spec["Cpk"]])
ax.axhline(1.33, linestyle="--")
st.pyplot(fig)
