import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from msal import ConfidentialClientApplication
import requests
from io import BytesIO

# =========================================================
# APP SETUP
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
# MS GRAPH AUTH
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
    "ALPLA HEFEI": "/sites/GLB-Quality-Alpla_Hefei",
    "ALPLA BRAZIL": "/sites/GLB-Quality-Alpla_Brazil",
    "ALPLA WAIDHOFEN": "/sites/GLB-Quality-Alpla_Waidhofen"
}

site_name = st.sidebar.selectbox("Site", list(sites.keys()))
site_path = sites[site_name]

# =========================================================
# GET SITE ID
# =========================================================
def get_site_id():
    url = f"https://graph.microsoft.com/v1.0/sites/sigitglobal.sharepoint.com:{site_path}"
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        st.error(r.text)
        st.stop()

    return r.json()["id"]

SITE_ID = get_site_id()

# =========================================================
# DRIVE
# =========================================================
def get_drive():
    url = f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drive"
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        st.error(r.text)
        st.stop()

    return r.json()

drive = get_drive()
DRIVE_ID = drive["id"]

# =========================================================
# SAFE PATH READER
# =========================================================
def list_folder(path):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/{path}:/children"
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        st.error(f"Folder not found: {path}")
        st.error(r.text)
        st.stop()

    return r.json()["value"]

# =========================================================
# BASE STRUCTURE
# =========================================================
BASE = "Quality Files Exchange"
YEAR = "2026"

year_children = list_folder(BASE)
year_folder = next((x for x in year_children if x["name"] == YEAR), None)

if not year_folder:
    st.error("2026 not found")
    st.stop()

# =========================================================
# LINE SELECTION
# =========================================================
lines = list_folder(f"{BASE}/{YEAR}")
lines = [x for x in lines if "folder" in x]

selected_line = st.sidebar.selectbox("Line", [l["name"] for l in lines])

# =========================================================
# FILES
# =========================================================
files = {
    "Cap": "Cap-Measurements&Specs.xlsx",
    "Flange": "Flange-Measurements&Specs.xlsx",
    "Cutting Ring": "Cutting-Ring-Measurements&Specs.xlsx"
}

selected_dataset = st.sidebar.selectbox("Dataset", list(files.keys()))
file_name = files[selected_dataset]

file_path = f"{BASE}/{YEAR}/{selected_line}/{file_name}"

# =========================================================
# DOWNLOAD FILE
# =========================================================
def download_file(path):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/{path}:/content"
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
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
# SPC CALC
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
# CAPABILITY
# =========================================================
def capability(x):
    if pd.isna(x):
        return "No data"
    if x >= 1.67:
        return "Excellent"
    if x >= 1.33:
        return "Capable"
    if x >= 1:
        return "Marginal"
    return "Not capable"

stats["Capability"] = stats["Cpk"].apply(capability)

# =========================================================
# STYLE TABLE (COLOR + BOLD)
# =========================================================
def style(df):
    s = pd.DataFrame("", index=df.index, columns=df.columns)

    s.loc[df["Capability"] == "Excellent", "Capability"] = "color:green;font-weight:bold"
    s.loc[df["Capability"] == "Capable", "Capability"] = "color:goldenrod;font-weight:bold"
    s.loc[df["Capability"] == "Marginal", "Capability"] = "color:orange;font-weight:bold"
    s.loc[df["Capability"] == "Not capable", "Capability"] = "color:red;font-weight:bold"

    return s

st.subheader("SPC Summary")
st.dataframe(stats.style.apply(style, axis=None), use_container_width=True)

# =========================================================
# CHARTS
# =========================================================
st.markdown("## Measurement Point")

char = st.selectbox("Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

col1, col2 = st.columns(2)

# =========================================================
# TREND CHART
# =========================================================
with col1:
    fig, ax = plt.subplots()

    ax.plot(values.values, label="Values", linewidth=2)
    ax.axhline(spec["Mean"], label="Mean", linewidth=2)
    ax.axhline(spec["USL"], linestyle="--", label="USL")
    ax.axhline(spec["LSL"], linestyle="--", label="LSL")

    ax.set_title(f"{char} Trend")
    ax.legend()
    ax.grid(alpha=0.3)

    st.pyplot(fig)

# =========================================================
# DISTRIBUTION CHART
# =========================================================
with col2:
    fig, ax = plt.subplots()

    ax.hist(values, bins=20, density=True, alpha=0.6, label="Distribution")

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        ax.plot(x, norm.pdf(x, values.mean(), values.std()), label="Normal Fit")

    ax.set_title("Distribution")
    ax.legend()
    ax.grid(alpha=0.3)

    st.pyplot(fig)
