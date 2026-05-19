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
# ACCESS PASSWORD GATE
# =========================================================
PASSWORD = "ShowRepoGQM31" 

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:

    st.subheader("Confidential Data - Access Required")

    pwd = st.text_input("Enter password - Ask any GQM team memnber for extra info", type="password")

    if st.button("Login"):

        if pwd == PASSWORD:
            st.session_state.auth = True
            st.success("Access granted")
            st.rerun()

        else:
            st.error("Wrong password")
            st.stop()

    st.stop()

# =========================================================
# AUTH
# =========================================================
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
TENANT_ID = st.secrets["TENANT_ID"]

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

token = app.acquire_token_for_client(scopes=SCOPES)

if "access_token" not in token:
    st.error("Authentication failed")
    st.write(token)
    st.stop()

headers = {"Authorization": f"Bearer {token['access_token']}"}

# =========================================================
# SHAREPOINT SITES
# =========================================================
sites = {
    "ALPLA HEFEI": {
        "site_id": "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Hefei:",
        "folder": "Measurements-test files"
    },
    "ALPLA BRAZIL": {
        "site_id": "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Brazil:",
        "folder": "Measurements-test files"
    },
    "ALPLA WAIDHOFEN": {
        "site_id": "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Waidhofen:",
        "folder": "2026"
    }
}

selected_site = st.sidebar.selectbox(
    "Select SharePoint Site",
    list(sites.keys())
)

SITE_ID = sites[selected_site]["site_id"]
FOLDER_NAME = sites[selected_site]["folder"]

# =========================================================
# GET DRIVE
# =========================================================
@st.cache_data
def get_drive(site_id):

    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Failed loading drives")
        st.stop()

    drives = res.json()["value"]

    for d in drives:
        if d["name"] in ["Documents", "Shared Documents"]:
            return d

    return drives[0]

drive = get_drive(SITE_ID)
DRIVE_ID = drive["id"]

# =========================================================
# FIND FOLDER (UNCHANGED)
# =========================================================
@st.cache_data
def find_folder(drive_id, folder_name):

    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/search(q='{folder_name}')"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Folder search failed")
        st.stop()

    items = res.json().get("value", [])

    for i in items:
        if "folder" in i and i["name"] == folder_name:
            return i["id"]

    st.error("Folder not found")
    st.stop()

# =========================================================
# LIST FILES (UNCHANGED FOR HEFEI/BRAZIL)
# =========================================================
@st.cache_data
def list_files(drive_id, folder_name):

    folder_id = find_folder(drive_id, folder_name)

    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}/children"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Cannot read folder content")
        st.stop()

    return res.json().get("value", [])

# =========================================================
# WAIDHOFEN FIX (REAL GRAPH STRUCTURE)
# =========================================================
if selected_site == "ALPLA WAIDHOFEN":

    # 1. ROOT → includes "2026"
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root/children"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Cannot load root folders")
        st.stop()

    root_items = res.json().get("value", [])
    root_folders = [x for x in root_items if "folder" in x]

    selected_root = st.sidebar.selectbox(
        "Folder",
        [f["name"] for f in root_folders]
    )

    root_folder = next(f for f in root_folders if f["name"] == selected_root)
    root_id = root_folder["id"]

    # 2. LINES inside 2026
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{root_id}/children"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Cannot load line folders")
        st.stop()

    line_items = res.json().get("value", [])
    line_folders = [x for x in line_items if "folder" in x]

    selected_line = st.sidebar.selectbox(
        "Line",
        [l["name"] for l in line_folders]
    )

    line_folder = next(l for l in line_folders if l["name"] == selected_line)
    line_id = line_folder["id"]

    # 3. FILES inside line folder
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{line_id}/children"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Cannot load files")
        st.stop()

    files_in_folder = res.json().get("value", [])

else:
    files_in_folder = list_files(DRIVE_ID, FOLDER_NAME)

# =========================================================
# FILES
# =========================================================
files = {
    "Dataset 0": "Test-Measurements&Specs.xlsx",
    "Dataset 1": "Test-Measurements&Specs1.xlsx",
    "Dataset 2": "Test-Measurements&Specs2.xlsx"
}

selected_dataset = st.sidebar.selectbox(
    "Select Dataset",
    list(files.keys())
)

selected_file = files[selected_dataset]

# =========================================================
# GET FILE
# =========================================================
def get_file_id(file_name):

    for f in files_in_folder:
        if f["name"] == file_name:
            return f["id"]

    st.error("File not found")
    st.stop()

file_id = get_file_id(selected_file)

# =========================================================
# DOWNLOAD
# =========================================================
def download_file(file_id):

    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{file_id}/content"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Download failed")
        st.stop()

    return BytesIO(res.content)

excel = download_file(file_id)

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
st.sidebar.header("Filters")

start_date, end_date = st.sidebar.date_input(
    "Date Range",
    value=(df["DATE"].min(), df["DATE"].max())
)

df = df[
    (df["DATE"] >= pd.to_datetime(start_date)) &
    (df["DATE"] <= pd.to_datetime(end_date))
]

materials = sorted(df["RAW MATERIAL"].dropna().unique())
colors = sorted(df["COLOR"].dropna().unique())

selected_rm = st.sidebar.multiselect("Raw Material", materials, default=materials)
selected_color = st.sidebar.multiselect("Color", colors, default=colors)

df = df[
    df["RAW MATERIAL"].isin(selected_rm) &
    df["COLOR"].isin(selected_color)
]

# =========================================================
# LIMITS
# =========================================================
df["USL"] = df["Target"] + df["Upper Dev"]
df["LSL"] = df["Target"] + df["Lower Dev"]

# =========================================================
# STATS
# =========================================================
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

above = df[df["Value"] > df["USL"]].groupby("Characteristic")["Value"].count()
below = df[df["Value"] < df["LSL"]].groupby("Characteristic")["Value"].count()

stats["Above OOS"] = stats["Characteristic"].map(above).fillna(0).astype(int)
stats["Below OOS"] = stats["Characteristic"].map(below).fillna(0).astype(int)

def capability(cpk):
    if pd.isna(cpk):
        return "No data"
    if cpk >= 1.67:
        return "Excellent"
    if cpk >= 1.33:
        return "Capable"
    if cpk >= 1:
        return "Marginal"
    return "Not capable"

stats["Process Capability"] = stats["Cpk"].apply(capability)

# =========================================================
# STYLE TABLE
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

# =========================================================
# OUTPUT
# =========================================================
st.subheader("SPC Summary")
st.dataframe(stats.style.apply(style, axis=None), use_container_width=True)

st.markdown("## Measurement Point")

char = st.selectbox("Select Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

col1, col2 = st.columns(2)

with col1:
    fig, ax = plt.subplots()

    ax.plot(values.values, color="#8e44ad", linewidth=1.8, label="Values")
    ax.axhline(spec["Mean"], color="#27ae60", label="Mean")
    ax.axhline(spec["USL"], color="#e74c3c", linestyle="--", label="USL")
    ax.axhline(spec["LSL"], color="#f39c12", linestyle="--", label="LSL")

    ax.set_title("Control Chart")
    ax.grid(alpha=0.3)
    ax.legend()

    st.pyplot(fig)

with col2:
    fig, ax = plt.subplots()

    ax.hist(values, bins=20, density=True, alpha=0.65, color="#3498db", edgecolor="black")

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        ax.plot(x, norm.pdf(x, values.mean(), values.std()), color="#8e44ad", label="Normal Fit")

    ax.set_title("Histogram")
    ax.grid(alpha=0.3)
    ax.legend()

    st.pyplot(fig)
