import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from msal import ConfidentialClientApplication
import requests
from io import BytesIO

# =========================================================
# PAGE
# =========================================================
st.set_page_config(page_title="SPC Dashboard", layout="wide")
st.title("SPC Dashboard")

# =========================================================
# PASSWORD
# =========================================================
PASSWORD = "ShowRepoGQM31"

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.subheader("Confidential Data - Access Required")
    pwd = st.text_input("Enter password", type="password")

    if st.button("Login"):
        if pwd == PASSWORD:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Wrong password")
            st.stop()

    st.stop()

# =========================================================
# AUTH MICROSOFT GRAPH
# =========================================================
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
TENANT_ID = st.secrets["TENANT_ID"]

app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    client_credential=CLIENT_SECRET
)

token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

if "access_token" not in token:
    st.error("Auth failed")
    st.stop()

headers = {"Authorization": f"Bearer {token['access_token']}"}

# =========================================================
# SITES
# =========================================================
sites = {
    "ALPLA HEFEI": "GLB-Quality-Alpla_Hefei",
    "ALPLA BRAZIL": "GLB-Quality-Alpla_Brazil",
    "ALPLA WAIDHOFEN": "GLB-Quality-Alpla_Waidhofen"
}

site_name = st.sidebar.selectbox("Site", list(sites.keys()))
site_path = sites[site_name]

# =========================================================
# GET DEFAULT DRIVE (IMPORTANT FIX)
# =========================================================
def get_drive():
    url = f"https://graph.microsoft.com/v1.0/sites/{site_path}/drive"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        st.error(r.text)
        st.stop()
    return r.json()

drive = get_drive()
DRIVE_ID = drive["id"]

# =========================================================
# PATH BASED ACCESS (NO SEARCH ANYMORE)
# =========================================================
BASE_FOLDER = "Quality Files Exchange"
YEAR = "2026"

def get_children_by_path(path):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/{path}:/children"
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        st.error(f"Path error: {path}")
        st.error(r.text)
        st.stop()

    return r.json()["value"]

# =========================================================
# YEAR LEVEL
# =========================================================
year_children = get_children_by_path(BASE_FOLDER)
year_folder = next((x for x in year_children if x["name"] == YEAR), None)

if not year_folder:
    st.error("2026 folder missing")
    st.stop()

# =========================================================
# LINE LEVEL
# =========================================================
line_children = get_children_by_path(f"{BASE_FOLDER}/{YEAR}")

lines = [x for x in line_children if "folder" in x]

selected_line = st.sidebar.selectbox("Line", [l["name"] for l in lines])
LINE = selected_line

# =========================================================
# FILES
# =========================================================
files = {
    "Cap": "Cap-Measurements&Specs.xlsx",
    "Flange": "Flange-Measurements&Specs.xlsx",
    "Cutting Ring": "Cutting-Ring-Measurements&Specs.xlsx"
}

selected_dataset = st.sidebar.selectbox("Dataset", list(files.keys()))
selected_file = files[selected_dataset]

file_path = f"{BASE_FOLDER}/{YEAR}/{LINE}/{selected_file}"

def download_file(path):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/{path}:/content"
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        st.error("Download failed")
        st.error(r.text)
        st.stop()

    return BytesIO(r.content)

excel = download_file(file_path)

# =========================================================
# LOAD DATA
# =========================================================
df_meas = pd.read_excel(excel, sheet_name="Measurements")
excel.seek(0)
df_specs = pd.read_excel(excel, sheet_name="Specs")

df_meas.columns = df_meas.columns.str.strip()
df_specs.columns = df_specs.columns.str.strip()

df_meas["DATE"] = pd.to_datetime(df_meas["DATE"])

# =========================================================
# TRANSFORM
# =========================================================
df_long = df_meas.melt(
    id_vars=["DATE", "RAW MATERIAL", "COLOR", "CAV"],
    var_name="Characteristic",
    value_name="Value"
)

df = df_long.merge(df_specs, on="Characteristic", how="left")

# =========================================================
# FILTERS
# =========================================================
start, end = st.sidebar.date_input(
    "Date range",
    value=(df["DATE"].min(), df["DATE"].max())
)

df = df[(df["DATE"] >= pd.to_datetime(start)) & (df["DATE"] <= pd.to_datetime(end))]

materials = df["RAW MATERIAL"].dropna().unique()
colors = df["COLOR"].dropna().unique()

df = df[
    df["RAW MATERIAL"].isin(st.sidebar.multiselect("Material", materials, default=materials)) &
    df["COLOR"].isin(st.sidebar.multiselect("Color", colors, default=colors))
]

# =========================================================
# STATS
# =========================================================
df["USL"] = df["Target"] + df["Upper Dev"]
df["LSL"] = df["Target"] + df["Lower Dev"]

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

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Std"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Mean"]) / (3 * stats["Std"]),
    (stats["Mean"] - stats["LSL"]) / (3 * stats["Std"])
)

st.dataframe(stats)

# =========================================================
# CHART
# =========================================================
char = st.selectbox("Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
values = data["Value"].dropna()

fig, ax = plt.subplots()
ax.plot(values.values)
ax.axhline(stats.loc[stats["Characteristic"] == char, "USL"].values[0], linestyle="--")
ax.axhline(stats.loc[stats["Characteristic"] == char, "LSL"].values[0], linestyle="--")
st.pyplot(fig)
