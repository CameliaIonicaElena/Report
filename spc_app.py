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
# AUTH
# =========================================================
PASSWORD = "ShowRepoGQM31"

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if pwd == PASSWORD:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Wrong password")
    st.stop()

# =========================================================
# GRAPH AUTH
# =========================================================
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
TENANT_ID = st.secrets["TENANT_ID"]

app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    client_credential=CLIENT_SECRET
)

token = app.acquire_token_for_client(["https://graph.microsoft.com/.default"])

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

site = st.sidebar.selectbox("Plant", list(sites.keys()))
site_path = sites[site]

site_id = f"sigitglobal.sharepoint.com:/sites/{site_path}:"

# =========================================================
# DRIVE
# =========================================================
def get_drive(site_id):
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()["value"][0]

drive = get_drive(site_id)
DRIVE_ID = drive["id"]

# =========================================================
# SAFE LIST ROOT (NO SEARCH)
# =========================================================
def list_children(item_id):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{item_id}/children"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json().get("value", [])

def find_by_name(items, name):
    for i in items:
        if i["name"] == name:
            return i
    return None

# =========================================================
# ROOT
# =========================================================
root = list_children("root")

qfe = find_by_name(root, "Quality Files Exchange")

# ❗ FALLBACK (DACA NU E IN ROOT)
if not qfe:
    st.error("Quality Files Exchange not found in root (checking all drives...)")

    drives = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives",
        headers=headers
    ).json()["value"]

    for d in drives:
        items = list_children(d["id"],) if False else []
    st.stop()

QFE_ID = qfe["id"]

# =========================================================
# YEAR
# =========================================================
qfe_children = list_children(QFE_ID)
year = find_by_name(qfe_children, "2026")

if not year:
    st.error("2026 not found")
    st.stop()

YEAR_ID = year["id"]

# =========================================================
# LINES
# =========================================================
lines = [x for x in list_children(YEAR_ID) if "folder" in x]

selected_line = st.sidebar.selectbox(
    "Line",
    [l["name"] for l in lines]
)

LINE_ID = next(l["id"] for l in lines if l["name"] == selected_line)

files = list_children(LINE_ID)

# =========================================================
# DATASET MAP
# =========================================================
dataset_map = {
    "Cap": "Cap-Measurements&Specs.xlsx",
    "Flange": "Flange-Measurements&Specs.xlsx",
    "Cutting Ring": "Cutting-Ring-Measurements&Specs.xlsx"
}

dataset = st.sidebar.selectbox("Dataset", list(dataset_map.keys()))
file_name = dataset_map[dataset]

file_id = next((f["id"] for f in files if f["name"] == file_name), None)

if not file_id:
    st.error(f"File not found: {file_name}")
    st.stop()

# =========================================================
# DOWNLOAD
# =========================================================
def download(file_id):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{file_id}/content"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return BytesIO(r.content)

excel = download(file_id)

# =========================================================
# DATA
# =========================================================
df = pd.read_excel(excel, sheet_name="Measurements")
excel.seek(0)
specs = pd.read_excel(excel, sheet_name="Specs")

df.columns = df.columns.str.strip()
specs.columns = specs.columns.str.strip()

df["DATE"] = pd.to_datetime(df["DATE"])

long = df.melt(
    id_vars=["DATE", "RAW MATERIAL", "COLOR", "CAV"],
    var_name="Characteristic",
    value_name="Value"
)

df = long.merge(specs, on="Characteristic", how="left")

# =========================================================
# FILTERS
# =========================================================
st.sidebar.header("Filters")

start, end = st.sidebar.date_input(
    "Date",
    value=(df["DATE"].min(), df["DATE"].max())
)

df = df[(df["DATE"] >= pd.to_datetime(start)) &
        (df["DATE"] <= pd.to_datetime(end))]

rm = st.sidebar.multiselect("Raw Material", df["RAW MATERIAL"].unique(), df["RAW MATERIAL"].unique())
col = st.sidebar.multiselect("Color", df["COLOR"].unique(), df["COLOR"].unique())

df = df[df["RAW MATERIAL"].isin(rm) & df["COLOR"].isin(col)]

# =========================================================
# STATS
# =========================================================
df["USL"] = df["Target"] + df["Upper Dev"]
df["LSL"] = df["Target"] + df["Lower Dev"]

g = df.groupby("Characteristic")

stats = pd.DataFrame({
    "Characteristic": g["Value"].count().index,
    "Mean": g["Value"].mean(),
    "Std": g["Value"].std(),
    "USL": g["USL"].first(),
    "LSL": g["LSL"].first(),
}).reset_index(drop=True)

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Std"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Mean"]) / (3 * stats["Std"]),
    (stats["Mean"] - stats["LSL"]) / (3 * stats["Std"])
)

# =========================================================
# UI
# =========================================================
st.subheader("SPC Summary")
st.dataframe(stats)

char = st.selectbox("Characteristic", stats["Characteristic"])

d = df[df["Characteristic"] == char]
s = stats[stats["Characteristic"] == char].iloc[0]
v = d["Value"].dropna()

col1, col2 = st.columns(2)

with col1:
    fig, ax = plt.subplots()
    ax.plot(v.values)
    ax.axhline(s["Mean"])
    ax.axhline(s["USL"], linestyle="--")
    ax.axhline(s["LSL"], linestyle="--")
    st.pyplot(fig)

with col2:
    fig, ax = plt.subplots()
    ax.hist(v, bins=20, density=True)
    if len(v) > 1:
        x = np.linspace(v.min(), v.max(), 100)
        ax.plot(x, norm.pdf(x, v.mean(), v.std()))
    st.pyplot(fig)
