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
# MSAL AUTH
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
# SITES (SAFE)
# =========================================================
sites = {
    "ALPLA HEFEI": "GLB-Quality-Alpla_Hefei",
    "ALPLA BRAZIL": "GLB-Quality-Alpla_Brazil",
    "ALPLA WAIDHOFEN": "GLB-Quality-Alpla_Waidhofen"
}

site_name = st.sidebar.selectbox("Site", list(sites.keys()))
site_path = sites[site_name]

# =========================================================
# GET SITE ID (FIXED PROPERLY)
# =========================================================
def get_site_id(site_path):
    url = f"https://graph.microsoft.com/v1.0/sites/sigitglobal.sharepoint.com:/sites/{site_path}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        st.error(r.text)
        st.stop()
    return r.json()["id"]

SITE_ID = get_site_id(site_path)

# =========================================================
# GET ALL DRIVES (ROBUST)
# =========================================================
def get_drive(site_id):
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    r = requests.get(url, headers=headers)
    return r.json()["value"]

drives = get_drive(SITE_ID)
DRIVE_ID = drives[0]["id"]

# =========================================================
# FIND FOLDER ROBUST (NO SEARCH BUGS)
# =========================================================
def find_folder_recursive(drive_id, folder_name):
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
    r = requests.get(url, headers=headers)
    items = r.json().get("value", [])

    for i in items:
        if i["name"] == folder_name:
            return i

    # fallback deep search
    for i in items:
        if "folder" in i:
            sub = requests.get(
                f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{i['id']}/children",
                headers=headers
            ).json().get("value", [])

            for s in sub:
                if s["name"] == folder_name:
                    return s

    return None

# =========================================================
# ROOT FOLDER
# =========================================================
qfe = find_folder_recursive(DRIVE_ID, "Quality Files Exchange")

if not qfe:
    st.error("Quality Files Exchange NOT FOUND (even in root children)")
    st.stop()

QFE_ID = qfe["id"]

# =========================================================
# YEAR
# =========================================================
children = requests.get(
    f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{QFE_ID}/children",
    headers=headers
).json().get("value", [])

year = next((x for x in children if x["name"] == "2026"), None)

if not year:
    st.error("2026 not found")
    st.stop()

YEAR_ID = year["id"]

# =========================================================
# LINE
# =========================================================
lines = requests.get(
    f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{YEAR_ID}/children",
    headers=headers
).json().get("value", [])

lines = [x for x in lines if "folder" in x]

selected_line = st.sidebar.selectbox("Line", [l["name"] for l in lines])
LINE_ID = next(l["id"] for l in lines if l["name"] == selected_line)

# =========================================================
# FILES
# =========================================================
files_in_folder = requests.get(
    f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{LINE_ID}/children",
    headers=headers
).json().get("value", [])

files = {
    "Cap": "Cap-Measurements&Specs.xlsx",
    "Flange": "Flange-Measurements&Specs.xlsx",
    "Cutting Ring": "Cutting-Ring-Measurements&Specs.xlsx"
}

selected_file = files[st.sidebar.selectbox("Dataset", list(files.keys()))]

file_id = next(f["id"] for f in files_in_folder if f["name"] == selected_file)

# =========================================================
# DOWNLOAD
# =========================================================
content = requests.get(
    f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{file_id}/content",
    headers=headers
).content

excel = BytesIO(content)

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
start, end = st.sidebar.date_input("Date range", (df["DATE"].min(), df["DATE"].max()))

df = df[(df["DATE"] >= pd.to_datetime(start)) & (df["DATE"] <= pd.to_datetime(end))]

materials = st.sidebar.multiselect("Material", df["RAW MATERIAL"].dropna().unique(), default=df["RAW MATERIAL"].dropna().unique())
colors = st.sidebar.multiselect("Color", df["COLOR"].dropna().unique(), default=df["COLOR"].dropna().unique())

df = df[df["RAW MATERIAL"].isin(materials) & df["COLOR"].isin(colors)]

# =========================================================
# SPC
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
})

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Std"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Mean"]) / (3 * stats["Std"]),
    (stats["Mean"] - stats["LSL"]) / (3 * stats["Std"])
)

def cap(x):
    if pd.isna(x): return "No data"
    if x >= 1.67: return "Excellent"
    if x >= 1.33: return "Capable"
    if x >= 1: return "Marginal"
    return "Not capable"

stats["Capability"] = stats["Cpk"].apply(cap)

# =========================================================
# UI TABLE STYLE (RESTORED)
# =========================================================
def style(df):
    s = pd.DataFrame("", index=df.index, columns=df.columns)
    s.loc[df["Capability"] == "Excellent", "Capability"] = "color:green;font-weight:bold"
    s.loc[df["Capability"] == "Capable", "Capability"] = "color:goldenrod;font-weight:bold"
    s.loc[df["Capability"] == "Marginal", "Capability"] = "color:orange;font-weight:bold"
    s.loc[df["Capability"] == "Not capable", "Capability"] = "color:red;font-weight:bold"
    return s

st.dataframe(stats.style.apply(style, axis=None), use_container_width=True)

# =========================================================
# CHARTS (RESTORED DESIGN)
# =========================================================
char = st.selectbox("Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

col1, col2 = st.columns(2)

with col1:
    fig, ax = plt.subplots()
    ax.plot(values.values, label="Values")
    ax.axhline(spec["Mean"], label="Mean")
    ax.axhline(spec["USL"], linestyle="--", label="USL")
    ax.axhline(spec["LSL"], linestyle="--", label="LSL")
    ax.legend()
    ax.grid()
    st.pyplot(fig)

with col2:
    fig, ax = plt.subplots()
    ax.hist(values, bins=20, density=True, alpha=0.6)

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        ax.plot(x, norm.pdf(x, values.mean(), values.std()))

    ax.grid()
    st.pyplot(fig)
