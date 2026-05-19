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
# LOGIN
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
            st.success("Access granted")
            st.rerun()
        else:
            st.error("Wrong password")
            st.stop()

    st.stop()

# =========================================================
# GRAPH AUTH
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

selected_site = st.sidebar.selectbox("Select Site", list(sites.keys()))
SITE_ID = sites[selected_site]

# =========================================================
# DRIVE
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
# LIST CHILDREN (GENERIC)
# =========================================================
@st.cache_data
def list_children_by_path(drive_id, path):
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{path}:/children"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error(f"Cannot load: {path}")
        st.stop()

    return res.json().get("value", [])

# =========================================================
# YEAR LEVEL (AUTO DETECT)
# =========================================================
year_items = list_children_by_path(DRIVE_ID, "")

year_folders = [x for x in year_items if "folder" in x]

year_names = [y["name"] for y in year_folders]

selected_year = st.sidebar.selectbox("Select Year", year_names)

# =========================================================
# LINE LEVEL
# =========================================================
line_items = list_children_by_path(DRIVE_ID, selected_year)

line_folders = [x for x in line_items if "folder" in x]

line_names = [l["name"] for l in line_folders]

selected_line = st.sidebar.selectbox("Select Line", line_names)

# =========================================================
# FILE LEVEL
# =========================================================
file_items = list_children_by_path(DRIVE_ID, f"{selected_year}/{selected_line}")

files = [x for x in file_items if "file" in x]

file_names = [f["name"] for f in files]

selected_file = st.sidebar.selectbox("Select Dataset", file_names)

file_id = next(f["id"] for f in files if f["name"] == selected_file)

# =========================================================
# DOWNLOAD FILE
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
# LOAD DATA (UNCHANGED)
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
# SPECS
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

# =========================================================
# OOS
# =========================================================
above = df[df["Value"] > df["USL"]].groupby("Characteristic")["Value"].count()
below = df[df["Value"] < df["LSL"]].groupby("Characteristic")["Value"].count()

stats["Above OOS"] = stats["Characteristic"].map(above).fillna(0).astype(int)
stats["Below OOS"] = stats["Characteristic"].map(below).fillna(0).astype(int)

# =========================================================
# CAPABILITY
# =========================================================
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
# OUTPUT
# =========================================================
st.subheader("SPC Summary")
st.dataframe(stats, use_container_width=True)

st.markdown("## Measurement Point")

char = st.selectbox("Select Characteristic", stats["Characteristic"])

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

    ax.set_title("Control Chart")
    st.pyplot(fig)

with col2:
    fig, ax = plt.subplots()

    ax.hist(values, bins=20, density=True, alpha=0.6)

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        ax.plot(x, norm.pdf(x, values.mean(), values.std()))

    ax.set_title("Histogram")
    st.pyplot(fig)
