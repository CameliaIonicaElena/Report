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
# SITE ID (FIXED)
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
# SAFE PATH (IMPORTANT FIX - NO SEARCH EVER)
# =========================================================
def list_folder(path):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/{path}:/children"
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        st.error(f"Folder not found: {path}")
        st.stop()

    return r.json()["value"]

BASE = "Quality Files Exchange"
YEAR = "2026"

# =========================================================
# YEAR
# =========================================================
year_folder = list_folder(BASE)
year_folder = next((x for x in year_folder if x["name"] == YEAR), None)

if not year_folder:
    st.error("2026 not found")
    st.stop()

# =========================================================
# LINE
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
# DOWNLOAD
# =========================================================
def download(path):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/{path}:/content"
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        st.error(r.text)
        st.stop()

    return BytesIO(r.content)

excel = download(file_path)

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

stats["Std"] = stats["Std"].replace(0, np.nan)

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Std"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Mean"]) / (3 * stats["Std"]),
    (stats["Mean"] - stats["LSL"]) / (3 * stats["Std"])
)

# =========================================================
# TABLE STYLE (KEEP COLORS)
# =========================================================
def style(df):
    s = pd.DataFrame("", index=df.index, columns=df.columns)

    s.loc[df["Cp"] > 1.33, "Cp"] = "color:blue;font-weight:bold"
    s.loc[df["Cpk"] < 1, "Cpk"] = "color:red;font-weight:bold"

    return s

st.subheader("SPC Summary")
st.dataframe(stats.style.apply(style, axis=None), use_container_width=True)

# =========================================================
# CHARACTERISTIC
# =========================================================
char = st.selectbox("Characteristic", stats["Characteristic"])

data = df[df["Characteristic"] == char]
values = data["Value"].dropna()

spec = stats[stats["Characteristic"] == char].iloc[0]

# =========================================================
# PLOTS (RESTORED ORIGINAL STYLE)
# =========================================================
col1, col2 = st.columns(2)

# ================= LEFT (LINE CHART)
with col1:
    fig, ax = plt.subplots()

    ax.plot(values.values, color="blue", label="Values")

    ax.axhline(spec["Mean"], color="blue", linestyle="-", linewidth=2, label="Mean")
    ax.axhline(spec["USL"], color="red", linestyle="--", label="USL")
    ax.axhline(spec["LSL"], color="red", linestyle="--", label="LSL")

    ax.fill_between(range(len(values)), spec["LSL"], spec["USL"], color="purple", alpha=0.08)

    ax.set_title("Trend")
    ax.grid(True)
    ax.legend(loc="upper right")

    st.pyplot(fig)

# ================= RIGHT (HISTOGRAM)
with col2:
    fig, ax = plt.subplots()

    ax.hist(values, bins=20, density=True, alpha=0.5, color="purple")

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        ax.plot(x, norm.pdf(x, values.mean(), values.std()), color="blue", label="Normal Fit")

    ax.set_title("Distribution")
    ax.grid(True)
    ax.legend()

    st.pyplot(fig)

# =========================================================
# LEGEND UNDER (SPC INFO STYLE)
# =========================================================
st.markdown("### SPC Legend")
st.markdown(
    """
    🔵 Blue = Process mean / values  
    🔴 Red = Specification limits (USL / LSL)  
    🟣 Purple area = tolerance zone  
    """
)
