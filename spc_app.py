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
# AUTH GATE
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
    "ALPLA HEFEI": "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Hefei:",
    "ALPLA BRAZIL": "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Brazil:",
    "ALPLA WAIDHOFEN": "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Waidhofen:"
}

selected_site = st.sidebar.selectbox("Site", list(sites.keys()))
SITE_ID = sites[selected_site]

# =========================================================
# DRIVE
# =========================================================
def get_drive(site_id):
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives",
        headers=headers
    )

    if r.status_code != 200:
        st.error(r.text)
        st.stop()

    return r.json()["value"][0]

drive = get_drive(SITE_ID)
DRIVE_ID = drive["id"]

# =========================================================
# SAFE CHILDREN
# =========================================================
def children(folder_id):
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{folder_id}/children",
        headers=headers
    )

    if r.status_code != 200:
        st.error(r.text)
        st.stop()

    return r.json().get("value", [])

# =========================================================
# ROOT
# =========================================================
root = children("root")

# =========================================================
# FIND "Shared Documents" FIRST (CRITICAL FIX)
# =========================================================
shared = next(
    (x for x in root if x.get("name") in ["Shared Documents", "Documents"]),
    None
)

if not shared:
    st.error("No document library found")
    st.stop()

shared_id = shared["id"]

# =========================================================
# NOW FIND QUALITY FILES EXCHANGE SAFELY
# =========================================================
qfe = next(
    (x for x in children(shared_id)
     if "Quality Files Exchange" in x.get("name", "")),
    None
)

if not qfe:
    st.error("Quality Files Exchange not found (check SharePoint library path)")
    st.stop()

qfe_id = qfe["id"]

# =========================================================
# YEAR 2026
# =========================================================
year = next(
    (x for x in children(qfe_id)
     if x.get("name") == "2026"),
    None
)

if not year:
    st.error("2026 not found")
    st.stop()

year_id = year["id"]

# =========================================================
# LINES
# =========================================================
lines = [x for x in children(year_id) if "folder" in x]

selected_line = st.sidebar.selectbox(
    "Line",
    [l["name"] for l in lines]
)

line_id = next(l["id"] for l in lines if l["name"] == selected_line)

# =========================================================
# FILES
# =========================================================
files = {
    "Cap": "Cap-Measurements&Specs.xlsx",
    "Flange": "Flange-Measurements&Specs.xlsx",
    "Cutting Ring": "Cutting-Ring-Measurements&Specs.xlsx"
}

selected = st.sidebar.selectbox("Dataset", list(files.keys()))
file_name = files[selected]

files_in_line = children(line_id)

file_id = next((f["id"] for f in files_in_line if f["name"] == file_name), None)

if not file_id:
    st.error(f"File not found: {file_name}")
    st.stop()

# =========================================================
# DOWNLOAD
# =========================================================
def download(fid):
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{fid}/content",
        headers=headers
    )

    if r.status_code != 200:
        st.error("Download failed")
        st.stop()

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

df = df_meas.melt(
    id_vars=["DATE", "RAW MATERIAL", "COLOR", "CAV"],
    var_name="Characteristic",
    value_name="Value"
).merge(df_specs, on="Characteristic", how="left")

# =========================================================
# FILTERS
# =========================================================
st.sidebar.header("Filters")

start, end = st.sidebar.date_input(
    "Date range",
    value=(df["DATE"].min(), df["DATE"].max())
)

df = df[(df["DATE"] >= pd.to_datetime(start)) & (df["DATE"] <= pd.to_datetime(end))]

rm = st.sidebar.multiselect(
    "Raw Material",
    sorted(df["RAW MATERIAL"].dropna().unique()),
    default=sorted(df["RAW MATERIAL"].dropna().unique())
)

col = st.sidebar.multiselect(
    "Color",
    sorted(df["COLOR"].dropna().unique()),
    default=sorted(df["COLOR"].dropna().unique())
)

df = df[df["RAW MATERIAL"].isin(rm) & df["COLOR"].isin(col)]

# =========================================================
# LIMITS
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

stats["Std"] = stats["Std"].replace(0, np.nan)

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Std"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Mean"]) / (3 * stats["Std"]),
    (stats["Mean"] - stats["LSL"]) / (3 * stats["Std"])
)

# =========================================================
# OOS + CAPABILITY
# =========================================================
above = df[df["Value"] > df["USL"]].groupby("Characteristic")["Value"].count()
below = df[df["Value"] < df["LSL"]].groupby("Characteristic")["Value"].count()

stats["Above OOS"] = stats["Characteristic"].map(above).fillna(0).astype(int)
stats["Below OOS"] = stats["Characteristic"].map(below).fillna(0).astype(int)

def cap(cpk):
    if pd.isna(cpk): return "No data"
    if cpk >= 1.67: return "Excellent"
    if cpk >= 1.33: return "Capable"
    if cpk >= 1: return "Marginal"
    return "Not capable"

stats["Process Capability"] = stats["Cpk"].apply(cap)

# =========================================================
# OUTPUT
# =========================================================
st.subheader("SPC Summary")
st.dataframe(stats)

char = st.selectbox("Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

col1, col2 = st.columns(2)

with col1:
    fig, ax = plt.subplots()
    ax.plot(values.values)
    ax.axhline(spec["Mean"])
    ax.axhline(spec["USL"], linestyle="--")
    ax.axhline(spec["LSL"], linestyle="--")
    ax.grid()
    st.pyplot(fig)

with col2:
    fig, ax = plt.subplots()
    ax.hist(values, bins=20, density=True)
    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        ax.plot(x, norm.pdf(x, values.mean(), values.std()))
    st.pyplot(fig)
