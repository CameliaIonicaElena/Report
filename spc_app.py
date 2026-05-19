import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from msal import ConfidentialClientApplication
import requests
from io import BytesIO

# =========================================================
# AUTH (UNCHANGED)
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

CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
TENANT_ID = st.secrets["TENANT_ID"]

app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    client_credential=CLIENT_SECRET
)

token = app.acquire_token_for_client(["https://graph.microsoft.com/.default"])
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
site_id = f"sigitglobal.sharepoint.com:/sites/{sites[site]}:"

# =========================================================
# DRIVE
# =========================================================
def get_drive(site_id):
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives",
        headers=headers
    )
    return r.json()["value"][0]

drive = get_drive(site_id)
DRIVE_ID = drive["id"]

# =========================================================
# SAFE LIST
# =========================================================
def children(item_id):
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{item_id}/children",
        headers=headers
    )
    return r.json().get("value", [])

def find(items, name):
    return next((x for x in items if x["name"] == name), None)

# =========================================================
# 🔥 FIX REAL: SEARCH ALL LEVELS (NO ROOT ASSUMPTION)
# =========================================================
def find_recursive(parent_id, target_name):
    items = children(parent_id)

    for i in items:
        if i["name"] == target_name:
            return i
        if "folder" in i:
            res = find_recursive(i["id"], target_name)
            if res:
                return res
    return None

# =========================================================
# START FROM DRIVE ROOT
# =========================================================
root_items = children("root")

qfe = find(root_items, "Quality Files Exchange")

# 🔥 FALLBACK IMPORTANT
if not qfe:
    # fallback: recursive search from root
    for i in root_items:
        if "folder" in i:
            qfe = find_recursive(i["id"], "Quality Files Exchange")
            if qfe:
                break

if not qfe:
    st.error("Quality Files Exchange NOT FOUND anywhere")
    st.stop()

# =========================================================
# YEAR
# =========================================================
year = find_recursive(qfe["id"], "2026")
if not year:
    st.error("2026 not found")
    st.stop()

# =========================================================
# LINE
# =========================================================
lines = [x for x in children(year["id"]) if "folder" in x]

line = st.sidebar.selectbox("Line", [l["name"] for l in lines])
line_id = next(l["id"] for l in lines if l["name"] == line)

files = children(line_id)

# =========================================================
# FILES
# =========================================================
map_files = {
    "Cap": "Cap-Measurements&Specs.xlsx",
    "Flange": "Flange-Measurements&Specs.xlsx",
    "Cutting Ring": "Cutting-Ring-Measurements&Specs.xlsx"
}

ds = st.sidebar.selectbox("Dataset", list(map_files.keys()))
fname = map_files[ds]

file_id = next((f["id"] for f in files if f["name"] == fname), None)

if not file_id:
    st.error("File missing")
    st.stop()

# =========================================================
# DOWNLOAD
# =========================================================
def download(fid):
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{fid}/content",
        headers=headers
    )
    return BytesIO(r.content)

excel = download(file_id)

# =========================================================
# DATA (UNCHANGED FROM YOUR WORKING LOGIC)
# =========================================================
df = pd.read_excel(excel, sheet_name="Measurements")
excel.seek(0)
specs = pd.read_excel(excel, sheet_name="Specs")

df.columns = df.columns.str.strip()
df["DATE"] = pd.to_datetime(df["DATE"])

long = df.melt(
    id_vars=["DATE", "RAW MATERIAL", "COLOR", "CAV"],
    var_name="Characteristic",
    value_name="Value"
)

df = long.merge(specs, on="Characteristic", how="left")

# =========================================================
# FILTERS + STATS (same logic)
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

df["USL"] = df["Target"] + df["Upper Dev"]
df["LSL"] = df["Target"] + df["Lower Dev"]

g = df.groupby("Characteristic")

stats = pd.DataFrame({
    "Characteristic": g["Value"].count().index,
    "Mean": g["Value"].mean(),
    "Std": g["Value"].std(),
    "USL": g["USL"].first(),
    "LSL": g["LSL"].first()
}).reset_index(drop=True)

st.subheader("SPC")
st.dataframe(stats)

char = st.selectbox("Characteristic", stats["Characteristic"])
d = df[df["Characteristic"] == char]

fig, ax = plt.subplots()
ax.plot(d["Value"].values)
st.pyplot(fig)
