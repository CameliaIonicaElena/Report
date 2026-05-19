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
    st.subheader("Access Required")

    pwd = st.text_input("Password", type="password")

    if st.button("Login"):
        if pwd == PASSWORD:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Wrong password")
            st.stop()

    st.stop()

# =========================================================
# MS AUTH
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
# PLANTS (KEEP WAIDHOFEN LOGIC = FIXED ROOT FOLDER)
# =========================================================
sites = {
    "ALPLA HEFEI": {
        "site_id": "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Hefei:",
        "folder": "Quality Files Exchange"
    },
    "ALPLA BRAZIL": {
        "site_id": "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Brazil:",
        "folder": "Quality Files Exchange"
    },
    "ALPLA WAIDHOFEN": {
        "site_id": "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Waidhofen:",
        "folder": "Quality Files Exchange"
    }
}

plant = st.sidebar.selectbox("Plant", list(sites.keys()))
SITE_ID = sites[plant]["site_id"]
ROOT_FOLDER = sites[plant]["folder"]

# =========================================================
# DRIVE
# =========================================================
def get_drive(site_id):
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    r = requests.get(url, headers=headers)
    return r.json()["value"][0]

drive = get_drive(SITE_ID)
DRIVE_ID = drive["id"]

# =========================================================
# SAFE FOLDER ACCESS (NO SEARCH - SAME LOGIC AS WAIDHOFEN)
# =========================================================
def children(folder_id):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{folder_id}/children"
    r = requests.get(url, headers=headers)
    return r.json().get("value", [])

def root_children():
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root/children"
    r = requests.get(url, headers=headers)
    return r.json().get("value", [])

# =========================================================
# STEP 1: FIND ROOT FOLDER (Quality Files Exchange)
# =========================================================
root = root_children()

qfe = next((x for x in root if x["name"] == ROOT_FOLDER), None)

if not qfe:
    st.error(f"{ROOT_FOLDER} not found in root")
    st.stop()

QFE_ID = qfe["id"]

# =========================================================
# STEP 2: YEAR = 2026
# =========================================================
qfe_children = children(QFE_ID)

year = next((x for x in qfe_children if x["name"] == "2026"), None)

if not year:
    st.error("2026 not found")
    st.stop()

YEAR_ID = year["id"]

# =========================================================
# STEP 3: LINES
# =========================================================
lines = [x for x in children(YEAR_ID) if "folder" in x]

line = st.sidebar.selectbox("Line", [l["name"] for l in lines])
LINE_ID = next(l["id"] for l in lines if l["name"] == line)

# =========================================================
# STEP 4: FILES
# =========================================================
files_in_folder = children(LINE_ID)

datasets = {
    "Cap": "Cap-Measurements&Specs.xlsx",
    "Flange": "Flange-Measurements&Specs.xlsx",
    "Cutting Ring": "Cutting-Ring-Measurements&Specs.xlsx"
}

dataset = st.sidebar.selectbox("Dataset", list(datasets.keys()))
file_name = datasets[dataset]

def get_file_id(name):
    for f in files_in_folder:
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
    return BytesIO(r.content)

excel = download(file_id)

# =========================================================
# DATA PROCESSING (UNCHANGED)
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
    "Date Range",
    value=(df["DATE"].min(), df["DATE"].max())
)

df = df[(df["DATE"] >= pd.to_datetime(start)) & (df["DATE"] <= pd.to_datetime(end))]

materials = st.sidebar.multiselect(
    "Raw Material",
    sorted(df["RAW MATERIAL"].dropna().unique()),
    default=sorted(df["RAW MATERIAL"].dropna().unique())
)

colors = st.sidebar.multiselect(
    "Color",
    sorted(df["COLOR"].dropna().unique()),
    default=sorted(df["COLOR"].dropna().unique())
)

df = df[df["RAW MATERIAL"].isin(materials) & df["COLOR"].isin(colors)]

# =========================================================
# STATS + LIMITS
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

def cap(x):
    if pd.isna(x): return "No data"
    if x >= 1.67: return "Excellent"
    if x >= 1.33: return "Capable"
    if x >= 1: return "Marginal"
    return "Not capable"

stats["Process Capability"] = stats["Cpk"].apply(cap)

# =========================================================
# STYLE
# =========================================================
def style(df):
    s = pd.DataFrame("", index=df.index, columns=df.columns)

    s.loc[df["Above OOS"] > 0, "Above OOS"] = "color:red;font-weight:bold"
    s.loc[df["Below OOS"] > 0, "Below OOS"] = "color:red;font-weight:bold"

    s.loc[df["Process Capability"] == "Excellent", "Process Capability"] = "color:green;font-weight:bold"
    s.loc[df["Process Capability"] == "Capable", "Process Capability"] = "color:goldenrod;font-weight:bold"
    s.loc[df["Process Capability"] == "Marginal", "Process Capability"] = "color:orange;font-weight:bold"
    s.loc[df["Process Capability"] == "Not capable", "Process Capability"] = "color:red;font-weight:bold"

    return s

st.subheader("SPC Summary")
st.dataframe(stats.style.apply(style, axis=None), use_container_width=True)

# =========================================================
# CHARTS
# =========================================================
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
    st.pyplot(fig)

with col2:
    fig, ax = plt.subplots()
    ax.hist(values, bins=20, density=True)

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        ax.plot(x, norm.pdf(x, values.mean(), values.std()))

    st.pyplot(fig)
