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

# =========================================================
# AUTH GRAPH
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

selected_site = st.sidebar.selectbox("Plant", list(sites.keys()))
site_name = sites[selected_site]

site_id_url = f"sigitglobal.sharepoint.com:/sites/{site_name}:"

# =========================================================
# DRIVE
# =========================================================
@st.cache_data
def get_drive(site_id):
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    r = requests.get(url, headers=headers)
    r.raise_for_status()

    for d in r.json()["value"]:
        if d["name"] in ["Documents", "Shared Documents"]:
            return d
    return r.json()["value"][0]

drive = get_drive(site_id_url)
DRIVE_ID = drive["id"]

# =========================================================
# SAFE LIST CHILDREN
# =========================================================
@st.cache_data
def list_children(drive_id, item_id):
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/children"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json().get("value", [])

# =========================================================
# FIND ROOT ITEM SAFELY (NO SEARCH)
# =========================================================
def find_item_by_name(children, name):
    for x in children:
        if x["name"] == name:
            return x
    return None

# =========================================================
# ROOT DRIVE ITEMS
# =========================================================
root_items = list_children(DRIVE_ID, "root")

shared_docs = find_item_by_name(root_items, "Shared Documents")
if not shared_docs:
    st.error("Shared Documents not found")
    st.stop()

# =========================================================
# QUALITY FILES EXCHANGE (SAFE NAVIGATION)
# =========================================================
shared_children = list_children(DRIVE_ID, shared_docs["id"])

qfe = find_item_by_name(shared_children, "Quality Files Exchange")

if not qfe:
    st.error("Quality Files Exchange NOT FOUND in Shared Documents")
    st.stop()

qfe_children = list_children(DRIVE_ID, qfe["id"])

# =========================================================
# YEAR (AUTO 2026)
# =========================================================
year = find_item_by_name(qfe_children, "2026")

if not year:
    st.error("2026 folder not found")
    st.stop()

year_children = list_children(DRIVE_ID, year["id"])

# =========================================================
# LINE SELECTION
# =========================================================
lines = [x for x in year_children if "folder" in x]

selected_line = st.sidebar.selectbox(
    "Line",
    [l["name"] for l in lines]
)

line_id = next(l["id"] for l in lines if l["name"] == selected_line)

files_in_line = list_children(DRIVE_ID, line_id)

# =========================================================
# DATASETS
# =========================================================
files_map = {
    "Cap": "Cap-Measurements&Specs.xlsx",
    "Flange": "Flange-Measurements&Specs.xlsx",
    "Cutting Ring": "Cutting-Ring-Measurements&Specs.xlsx"
}

dataset = st.sidebar.selectbox("Dataset", list(files_map.keys()))
file_name = files_map[dataset]

def get_file_id(name):
    for f in files_in_line:
        if f["name"] == name:
            return f["id"]
    st.error(f"File not found: {name}")
    st.stop()

file_id = get_file_id(file_name)

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
df_meas = pd.read_excel(excel, sheet_name="Measurements")
excel.seek(0)
df_specs = pd.read_excel(excel, sheet_name="Specs")

df_meas.columns = df_meas.columns.str.strip()
df_specs.columns = df_specs.columns.str.strip()

df_meas["DATE"] = pd.to_datetime(df_meas["DATE"])

df_long = df_meas.melt(
    id_vars=["DATE", "RAW MATERIAL", "COLOR", "CAV"],
    var_name="Characteristic",
    value_name="Value"
)

df = df_long.merge(df_specs, on="Characteristic", how="left")

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

rm = st.sidebar.multiselect(
    "Raw Material",
    sorted(df["RAW MATERIAL"].dropna().unique()),
    default=sorted(df["RAW MATERIAL"].dropna().unique())
)

color = st.sidebar.multiselect(
    "Color",
    sorted(df["COLOR"].dropna().unique()),
    default=sorted(df["COLOR"].dropna().unique())
)

df = df[df["RAW MATERIAL"].isin(rm) & df["COLOR"].isin(color)]

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
# OUTPUT
# =========================================================
st.subheader("SPC Summary")
st.dataframe(stats)

char = st.selectbox("Characteristic", stats["Characteristic"])

d = df[df["Characteristic"] == char]
s = stats[stats["Characteristic"] == char].iloc[0]
vals = d["Value"].dropna()

col1, col2 = st.columns(2)

with col1:
    fig, ax = plt.subplots()
    ax.plot(vals.values)
    ax.axhline(s["Mean"])
    ax.axhline(s["USL"], linestyle="--")
    ax.axhline(s["LSL"], linestyle="--")
    st.pyplot(fig)

with col2:
    fig, ax = plt.subplots()
    ax.hist(vals, bins=20, density=True)
    if len(vals) > 1:
        x = np.linspace(vals.min(), vals.max(), 100)
        ax.plot(x, norm.pdf(x, vals.mean(), vals.std()))
    st.pyplot(fig)
