import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
import requests
from msal import ConfidentialClientApplication
from io import BytesIO

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("SPC Dashboard")

# =========================
# SHAREPOINT CONFIG
# =========================
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
TENANT_ID = st.secrets["TENANT_ID"]

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

SCOPES = ["https://graph.microsoft.com/.default"]

SITE_ID = "sigitglobal.sharepoint.com:/sites/GQMSpouts131"

# =========================
# AUTH
# =========================
app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

token_response = app.acquire_token_for_client(scopes=SCOPES)

access_token = token_response["access_token"]

headers = {
    "Authorization": f"Bearer {access_token}"
}

# =========================
# FILES
# =========================
files = {
    "Dataset 0": "Test-Measurements&Specs.xlsx",
    "Dataset 1": "Test-Measurements&Specs1.xlsx",
    "Dataset 2": "Test-Measurements&Specs2.xlsx"
}

selected_file = st.sidebar.selectbox(
    "Select dataset",
    list(files.keys())
)

selected_filename = files[selected_file]

# =========================
# DOWNLOAD FILE FROM SP
# =========================
file_url = f"""
https://graph.microsoft.com/v1.0/sites/{SITE_ID}
/drive/root:/Shared Documents/Measurements-test files/{selected_filename}:/content
"""

file_url = file_url.replace("\n", "")

response = requests.get(file_url, headers=headers)

if response.status_code != 200:
    st.error("Failed to load SharePoint file")
    st.stop()

excel_data = BytesIO(response.content)

# =========================
# LOAD EXCEL
# =========================
df_meas = pd.read_excel(
    excel_data,
    sheet_name="Measurements"
)

excel_data.seek(0)

df_specs = pd.read_excel(
    excel_data,
    sheet_name="Specs"
)

df_meas.columns = df_meas.columns.str.strip()
df_specs.columns = df_specs.columns.str.strip()

df_meas["DATE"] = pd.to_datetime(df_meas["DATE"])

# =========================
# TRANSFORM
# =========================
df_long = df_meas.melt(
    id_vars=["DATE", "RAW MATERIAL", "COLOR", "CAV"],
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

min_d = df["DATE"].min()
max_d = df["DATE"].max()

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(min_d, max_d),
    min_value=min_d,
    max_value=max_d
)

df = df[
    (df["DATE"] >= pd.to_datetime(start_date)) &
    (df["DATE"] <= pd.to_datetime(end_date))
]

materials = sorted(df["RAW MATERIAL"].dropna().unique())
colors = sorted(df["COLOR"].dropna().unique())

if st.sidebar.checkbox("Select all RAW MATERIAL", True):
    selected_m = materials
else:
    selected_m = st.sidebar.multiselect(
        "RAW MATERIAL",
        materials,
        default=materials
    )

df = df[df["RAW MATERIAL"].isin(selected_m)]

if st.sidebar.checkbox("Select all COLOR", True):
    selected_c = colors
else:
    selected_c = st.sidebar.multiselect(
        "COLOR",
        colors,
        default=colors
    )

df = df[df["COLOR"].isin(selected_c)]

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

above = df[df["Value"] > df["USL"]] \
    .groupby("Characteristic")["Value"] \
    .count()

below = df[df["Value"] < df["LSL"]] \
    .groupby("Characteristic")["Value"] \
    .count()

stats["Above OOS"] = (
    stats["Characteristic"]
    .map(above)
    .fillna(0)
    .astype(int)
)

stats["Below OOS"] = (
    stats["Characteristic"]
    .map(below)
    .fillna(0)
    .astype(int)
)

# =========================
# TABLE STYLE
# =========================
def style(df):

    s = pd.DataFrame(
        "",
        index=df.index,
        columns=df.columns
    )

    s.loc[
        df["Above OOS"] > 0,
        "Above OOS"
    ] = "color:red;font-weight:bold;text-decoration:underline"

    s.loc[
        df["Below OOS"] > 0,
        "Below OOS"
    ] = "color:red;font-weight:bold;text-decoration:underline"

    return s

# =========================
# SUMMARY TABLE
# =========================
st.subheader("SPC Summary")

st.dataframe(
    stats.style.apply(style, axis=None),
    use_container_width=True
)

# =========================
# MEASUREMENT POINT
# =========================
st.markdown("## Measurement point")

char = st.selectbox(
    "Select measurement point",
    stats["Characteristic"]
)

data = df[df["Characteristic"] == char]

spec = stats[
    stats["Characteristic"] == char
].iloc[0]

values = data["Value"].dropna()

# =========================
# CONTROL + HIST
# =========================
c1, c2 = st.columns(2)

with c1:

    fig, ax = plt.subplots(figsize=(6, 4))

    ax.plot(
        values.values,
        marker="o",
        color="#1f77b4"
    )

    ax.axhline(
        spec["Mean"],
        color="green"
    )

    ax.axhline(
        spec["USL"],
        color="red",
        linestyle="--"
    )

    ax.axhline(
        spec["LSL"],
        color="red",
        linestyle="--"
    )

    ax.set_title("Control Chart")
    ax.grid()

    st.pyplot(fig)

with c2:

    fig, ax = plt.subplots(figsize=(6, 4))

    ax.hist(
        values,
        bins=20,
        density=True,
        alpha=0.6,
        color="#6baed6"
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
            color="purple"
        )

    ax.set_title("Histogram + Normal Curve")
    ax.grid()

    st.pyplot(fig)
