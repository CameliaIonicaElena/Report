import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from msal import ConfidentialClientApplication
import requests
from io import BytesIO

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("SPC Dashboard")

# =========================
# SECRETS (SAFE)
# =========================
CLIENT_ID = st.secrets.get("CLIENT_ID")
CLIENT_SECRET = st.secrets.get("CLIENT_SECRET")
TENANT_ID = st.secrets.get("TENANT_ID")
SITE_ID = st.secrets.get("SITE_ID")

if not all([CLIENT_ID, CLIENT_SECRET, TENANT_ID, SITE_ID]):
    st.error("Missing secrets (CLIENT_ID / CLIENT_SECRET / TENANT_ID / SITE_ID)")
    st.stop()

# =========================
# AUTH AZURE GRAPH
# =========================
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

token = app.acquire_token_for_client(scopes=SCOPES)

if "access_token" not in token:
    st.error("Azure authentication failed")
    st.write(token)
    st.stop()

headers = {"Authorization": f"Bearer {token['access_token']}"}

# =========================
# FILES (SharePoint)
# =========================
base_path = "Shared%20Documents/Measurements-test%20files"

files = {
    "Dataset 0": f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drive/root:/{base_path}/Test-Measurements&Specs.xlsx:/content",
    "Dataset 1": f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drive/root:/{base_path}/Test-Measurements&Specs1.xlsx:/content",
    "Dataset 2": f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drive/root:/{base_path}/Test-Measurements&Specs2.xlsx:/content"
}

# =========================
# SELECT FILE
# =========================
selected = st.sidebar.selectbox("Select dataset", list(files.keys()))
url = files[selected]

r = requests.get(url, headers=headers)

if r.status_code != 200:
    st.error("Failed loading SharePoint file")
    st.write(r.text)
    st.stop()

excel = BytesIO(r.content)

df_meas = pd.read_excel(excel, sheet_name="Measurements")
excel.seek(0)
df_specs = pd.read_excel(excel, sheet_name="Specs")

# =========================
# CLEAN
# =========================
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

df = df_long.merge(df_specs, on="Characteristic", how="left")

# =========================
# FILTERS
# =========================
st.sidebar.header("Filters")

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(df["DATE"].min(), df["DATE"].max())
)

df = df[df["DATE"].between(pd.to_datetime(start_date), pd.to_datetime(end_date))]

materials = sorted(df["RAW MATERIAL"].dropna().unique())
colors = sorted(df["COLOR"].dropna().unique())

selected_m = st.sidebar.multiselect("RAW MATERIAL", materials, default=materials)
selected_c = st.sidebar.multiselect("COLOR", colors, default=colors)

df = df[df["RAW MATERIAL"].isin(selected_m)]
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

stats["Cp"] = (stats["USL"] - stats["LSL"]) / (6 * stats["Std"])
stats["Cpk"] = np.minimum(
    (stats["USL"] - stats["Mean"]) / (3 * stats["Std"]),
    (stats["Mean"] - stats["LSL"]) / (3 * stats["Std"])
)

# =========================
# SELECT POINT
# =========================
st.markdown("## Measurement point")

char = st.selectbox("Select measurement point", stats["Characteristic"])

data = df[df["Characteristic"] == char]
spec = stats[stats["Characteristic"] == char].iloc[0]
values = data["Value"].dropna()

# =========================
# ROW 1
# =========================
c1, c2 = st.columns(2)

# CONTROL CHART
with c1:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.plot(values.values, marker="o", color="#1f77b4")
    ax.axhline(spec["Mean"], color="green", label="Mean")
    ax.axhline(spec["USL"], color="red", linestyle="--", label="USL")
    ax.axhline(spec["LSL"], color="orange", linestyle="--", label="LSL")

    ax.set_title("Control Chart")
    ax.grid(alpha=0.3)
    ax.legend()

    st.pyplot(fig)

# HISTOGRAM
with c2:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.hist(values, bins=20, density=True, alpha=0.6, color="#6baed6")

    if len(values) > 1:
        x = np.linspace(values.min(), values.max(), 100)
        ax.plot(x, norm.pdf(x, values.mean(), values.std()), color="purple")

    ax.set_title("Histogram + Normal Curve")
    ax.grid(alpha=0.3)

    st.pyplot(fig)

# =========================
# ROW 2
# =========================
c3, c4 = st.columns(2)

# I-MR
with c3:
    if len(values) > 1:
        mr = values.diff().abs().dropna()

        fig, ax = plt.subplots(2, 1, figsize=(6, 4), sharex=True)

        ax[0].plot(values.values, color="#1f77b4")
        ax[0].set_title("I Chart")
        ax[0].grid(alpha=0.3)

        ax[1].plot(mr.values, color="#ff7f0e")
        ax[1].set_title("Moving Range")
        ax[1].grid(alpha=0.3)

        st.pyplot(fig)

# CAPABILITY
with c4:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.bar(["Cp", "Cpk"], [spec["Cp"], spec["Cpk"]], color=["#1f77b4", "#17becf"])
    ax.axhline(1.33, linestyle="--", color="red")

    ax.set_title("Capability")
    ax.grid(axis="y", alpha=0.3)

    st.pyplot(fig)

# =========================
# GENERAL TEXT ONLY
# =========================
st.markdown("## General overview for selected closure")
st.info("Use filters and select measurement point to analyze SPC behavior.")
