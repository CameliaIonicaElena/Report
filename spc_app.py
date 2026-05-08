import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from msal import ConfidentialClientApplication
import requests
from io import BytesIO

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("SPC Dashboard")

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
    st.error("Auth failed")
    st.stop()

headers = {"Authorization": f"Bearer {token['access_token']}"}

# =========================
# GET DRIVE
# =========================
drive_url = f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drives"
drive = requests.get(drive_url, headers=headers).json()["value"][0]
DRIVE_ID = drive["id"]

st.sidebar.success(f"Drive: {drive['name']}")

# =========================
# FILE SEARCH (IMPORTANT FIX)
# =========================
def get_file_id(file_name):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root/search(q='{file_name}')"
    res = requests.get(url, headers=headers).json()

    items = res.get("value", [])

    if not items:
        st.error(f"File not found: {file_name}")
        st.stop()

    return items[0]["id"]

def download_file(file_id):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{file_id}/content"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error(res.text)
        st.stop()

    return BytesIO(res.content)
def list_all_files():
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root/children"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error(res.text)
        st.stop()

    return res.json()["value"]
# =========================
# FILES (EXACT CE AI DAT TU)
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

start, end = st.sidebar.date_input(
    "Date range",
    value=(df["DATE"].min(), df["DATE"].max())
)

df = df[(df["DATE"] >= pd.to_datetime(start)) &
        (df["DATE"] <= pd.to_datetime(end))]

materials = df["RAW MATERIAL"].dropna().unique()
colors = df["COLOR"].dropna().unique()

df = df[
    df["RAW MATERIAL"].isin(materials) &
    df["COLOR"].isin(colors)
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
    st.pyplot(fig)

with c2:
    fig, ax = plt.subplots()
    ax.hist(values, bins=20, density=True, alpha=0.6)

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        ax.plot(x, norm.pdf(x, values.mean(), values.std()))

    st.pyplot(fig)
