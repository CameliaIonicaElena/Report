import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from msal import ConfidentialClientApplication
import requests
from io import BytesIO

# =========================
# APP
# =========================
st.set_page_config(layout="wide")
st.title("SPC Dashboard")

# =========================
# AUTH
# =========================
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
TENANT_ID = st.secrets["TENANT_ID"]

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

SITE_ID = "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Hefei:"

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

# =========================
# GET DRIVE
# =========================
@st.cache_data
def get_drive():
    url = f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drives"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Failed loading SharePoint drives")
        st.write(res.text)
        st.stop()

    drives = res.json()["value"]

    for d in drives:
        if "Documents" in d["name"] or "Shared" in d["name"]:
            return d

    return drives[0]

drive = get_drive()
DRIVE_ID = drive["id"]

# =========================
# FOLDER
# =========================
FOLDER_PATH = "Measurements-test files"

@st.cache_data
def list_files():
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/{FOLDER_PATH}:/children"

    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Folder not found")
        st.write(res.text)
        st.stop()

    return res.json().get("value", [])

files_in_folder = list_files()

# =========================
# GET FILE ID
# =========================
def get_file_id(file_name):
    for f in files_in_folder:
        if f["name"] == file_name:
            return f["id"]

    st.error(f"File not found: {file_name}")
    st.write([f["name"] for f in files_in_folder])
    st.stop()

# =========================
# DOWNLOAD FILE
# =========================
def download_file(file_id):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{file_id}/content"

    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        st.error("Download failed")
        st.write(res.text)
        st.stop()

    return BytesIO(res.content)

# =========================
# FILES
# =========================
files = {
    "Dataset 0": "Test-Measurements&Specs.xlsx",
    "Dataset 1": "Test-Measurements&Specs1.xlsx",
    "Dataset 2": "Test-Measurements&Specs2.xlsx",
}

selected = st.sidebar.selectbox(
    "Select dataset",
    list(files.keys())
)

file_name = files[selected]

file_id = get_file_id(file_name)

excel = download_file(file_id)

# =========================
# SIDEBAR INFO
# =========================
st.sidebar.markdown("---")

st.sidebar.success("Connected")

st.sidebar.markdown(
    f"""
### Data Source

**Site**  
GLB-Quality-Alpla_Hefei

**Folder**  
{FOLDER_PATH}

**Dataset**  
{selected}

**File**  
{file_name}
"""
)

# =========================
# LOAD DATA
# =========================
df_meas = pd.read_excel(
    excel,
    sheet_name="Measurements"
)

excel.seek(0)

df_specs = pd.read_excel(
    excel,
    sheet_name="Specs"
)

df_meas.columns = df_meas.columns.str.strip()
df_specs.columns = df_specs.columns.str.strip()

df_meas["DATE"] = pd.to_datetime(df_meas["DATE"])

# =========================
# TRANSFORM
# =========================
df_long = df_meas.melt(
    id_vars=[
        "DATE",
        "RAW MATERIAL",
        "COLOR",
        "CAV"
    ],
    var_name="Characteristic",
    value_name="Value"
)

df = df_long.merge(
    df_specs,
    on="Characteristic",
    how="left"
)

# =========================
# FILTERS
# =========================
st.sidebar.header("Filters")

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(
        df["DATE"].min(),
        df["DATE"].max()
    ),
    min_value=df["DATE"].min(),
    max_value=df["DATE"].max()
)

df = df[
    (df["DATE"] >= pd.to_datetime(start_date)) &
    (df["DATE"] <= pd.to_datetime(end_date))
]

materials = sorted(
    df["RAW MATERIAL"].dropna().unique()
)

colors = sorted(
    df["COLOR"].dropna().unique()
)

# =========================
# RAW MATERIAL
# =========================
if st.sidebar.checkbox("All RM", True):
    selected_m = materials
else:
    selected_m = st.sidebar.multiselect(
        "Raw Material",
        materials,
        default=materials
    )

# =========================
# COLOR
# =========================
if st.sidebar.checkbox("All COLOR", True):
    selected_c = colors
else:
    selected_c = st.sidebar.multiselect(
        "Color",
        colors,
        default=colors
    )

df = df[
    df["RAW MATERIAL"].isin(selected_m) &
    df["COLOR"].isin(selected_c)
]

# =========================
# LIMITS
# =========================
df["USL"] = df["Target"] + df["Upper Dev"]
df["LSL"] = df["Target"] + df["Lower Dev"]

# =========================
# STATS
# =========================
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

stats["Cp"] = (
    (stats["USL"] - stats["LSL"]) /
    (6 * stats["Std"])
)

stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Mean"]) /
    (3 * stats["Std"]),

    (stats["Mean"] - stats["LSL"]) /
    (3 * stats["Std"])
)

# =========================
# OOS
# =========================
above = df[df["Value"] > df["USL"]] \
    .groupby("Characteristic")["Value"] \
    .count()

below = df[df["Value"] < df["LSL"]] \
    .groupby("Characteristic")["Value"] \
    .count()

stats["Above OOS"] = stats["Characteristic"] \
    .map(above) \
    .fillna(0) \
    .astype(int)

stats["Below OOS"] = stats["Characteristic"] \
    .map(below) \
    .fillna(0) \
    .astype(int)

# =========================
# PROCESS CAPABILITY
# =========================
def process_capability(cpk):

    if pd.isna(cpk):
        return None

    if cpk >= 1.67:
        return "Excellent"

    if cpk >= 1.33:
        return "Capable"

    if cpk >= 1:
        return "Marginal"

    return "Not capable"

stats["Process Capability"] = stats["Cpk"].apply(
    process_capability
)

# =========================
# STYLE TABLE
# =========================
def style_table(df_style):

    s = pd.DataFrame(
        "",
        index=df_style.index,
        columns=df_style.columns
    )

    s.loc[
        df_style["Above OOS"] > 0,
        "Above OOS"
    ] = "color:red;font-weight:bold"

    s.loc[
        df_style["Below OOS"] > 0,
        "Below OOS"
    ] = "color:red;font-weight:bold"

    s.loc[
        df_style["Process Capability"] == "Excellent",
        "Process Capability"
    ] = "color:green;font-weight:bold"

    s.loc[
        df_style["Process Capability"] == "Capable",
        "Process Capability"
    ] = "color:#1f77b4;font-weight:bold"

    s.loc[
        df_style["Process Capability"] == "Marginal",
        "Process Capability"
    ] = "color:orange;font-weight:bold"

    s.loc[
        df_style["Process Capability"] == "Not capable",
        "Process Capability"
    ] = "color:red;font-weight:bold"

    return s

# =========================
# SUMMARY
# =========================
st.subheader("SPC Summary")

st.dataframe(
    stats.style.apply(style_table, axis=None),
    use_container_width=True
)

# =========================
# MEASUREMENT POINT
# =========================
st.markdown("## Measurement Point")

char = st.selectbox(
    "Select characteristic",
    stats["Characteristic"]
)

data = df[
    df["Characteristic"] == char
]

spec = stats[
    stats["Characteristic"] == char
].iloc[0]

values = data["Value"].dropna()

# =========================
# CHARTS
# =========================
c1, c2 = st.columns(2)

# =========================
# CONTROL CHART
# =========================
with c1:

    fig, ax = plt.subplots(
        figsize=(6, 4)
    )

    ax.plot(
        values.values,
        color="#1f77b4",
        marker="o",
        linewidth=1.5
    )

    ax.axhline(
        spec["Mean"],
        color="green",
        linewidth=2
    )

    ax.axhline(
        spec["USL"],
        color="red",
        linestyle="--",
        linewidth=2
    )

    ax.axhline(
        spec["LSL"],
        color="orange",
        linestyle="--",
        linewidth=2
    )

    ax.set_title("Control Chart")

    ax.grid(alpha=0.3)

    st.pyplot(fig)

# =========================
# HISTOGRAM
# =========================
with c2:

    fig, ax = plt.subplots(
        figsize=(6, 4)
    )

    ax.hist(
        values,
        bins=20,
        density=True,
        alpha=0.6,
        color="#6BAED6",
        edgecolor="black"
    )

    if len(values) > 1:

        x = np.linspace(
            values.min(),
            values.max(),
            100
        )

        ax.plot(
            x,
            norm.pdf(
                x,
                values.mean(),
                values.std()
            ),
            color="purple",
            linewidth=2
        )

    ax.set_title("Histogram")

    ax.grid(alpha=0.3)

    st.pyplot(fig)
