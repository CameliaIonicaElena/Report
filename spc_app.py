import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from msal import ConfidentialClientApplication
import requests
from io import BytesIO
import urllib.parse

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("SPC Dashboard")

# =========================
# AZURE SECRETS
# =========================
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
TENANT_ID = st.secrets["TENANT_ID"]
SITE_ID = st.secrets["SITE_ID"]

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

# =========================
# AUTH
# =========================
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
# SHAREPOINT PATH
# =========================
base_path = "Shared Documents/Measurements-test files"

def graph_url(file):
    file_enc = urllib.parse.quote(file)
    path_enc = urllib.parse.quote(base_path)

    return (
        f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drive/root:"
        f"/{path_enc}/{file_enc}:/content"
    )

files = {
    "Dataset 0": graph_url("Test-Measurements&Specs.xlsx"),
    "Dataset 1": graph_url("Test-Measurements&Specs1.xlsx"),
    "Dataset 2": graph_url("Test-Measurements&Specs2.xlsx"),
}

# =========================
# SELECT FILE
# =========================
selected = st.sidebar.selectbox("Select dataset", list(files.keys()))
url = files[selected]

# =========================
# DOWNLOAD FILE
# =========================
res = requests.get(url, headers=headers)

if res.status_code != 200:
    st.error("Failed loading SharePoint file")
    st.write(res.text)
    st.stop()

excel = BytesIO(res.content)

df_meas = pd.read_excel(excel, sheet_name="Measurements")
excel.seek(0)
df_specs = pd.read_excel(excel, sheet_name="Specs")

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
# FILTERS (UNCHANGED)
# =========================
st.sidebar.header("Filters")

min_d, max_d = df["DATE"].min(), df["DATE"].max()

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(min_d, max_d),
    min_value=min_d,
    max_value=max_d
)

df = df[(df["DATE"] >= pd.to_datetime(start_date)) &
        (df["DATE"] <= pd.to_datetime(end_date))]

materials = sorted(df["RAW MATERIAL"].dropna().unique())
colors = sorted(df["COLOR"].dropna().unique())

selected_m = materials if st.sidebar.checkbox("Select all RAW MATERIAL", True) else st.sidebar.multiselect("RAW MATERIAL", materials, default=materials)
df = df[df["RAW MATERIAL"].isin(selected_m)]

selected_c = colors if st.sidebar.checkbox("Select all COLOR", True) else st.sidebar.multiselect("COLOR", colors, default=colors)
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

# =========================
# TABLE STYLE
# =========================
def style(df):
    s = pd.DataFrame("", index=df.index, columns=df.columns)
    s.loc[df["Above OOS"] > 0, "Above OOS"] = "color:red;font-weight:bold;text-decoration:underline"
    s.loc[df["Below OOS"] > 0, "Below OOS"] = "color:red;font-weight:bold;text-decoration:underline"
    return s

st.subheader("SPC Summary")
st.dataframe(stats.style.apply(style, axis=None), use_container_width=True)

# =========================
# MEASUREMENT POINT
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

with c1:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.plot(values.values, marker="o", color="#1f77b4")
    ax.axhline(spec["Mean"], color="green")
    ax.axhline(spec["USL"], color="red", linestyle="--")
    ax.axhline(spec["LSL"], color="orange", linestyle="--")

    ax.set_title("Control Chart")
    ax.grid(alpha=0.3)

    st.pyplot(fig)

with c2:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.hist(values, bins=20, density=True, alpha=0.6, color="#6BAED6")

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

with c4:
    fig, ax = plt.subplots(figsize=(6, 4))

    ax.bar(["Cp", "Cpk"], [spec["Cp"], spec["Cpk"]], color=["#1f77b4", "#17becf"])
    ax.axhline(1.33, color="red", linestyle="--")

    ax.set_title("Capability")
    ax.grid(alpha=0.3)

    st.pyplot(fig)

# =========================
# GLOBAL OVERVIEW
# =========================
st.markdown("## General overview")

c5, c6 = st.columns(2)

with c5:
    fig, ax = plt.subplots(figsize=(7, 4))
    df.boxplot(column="Value", by="Characteristic", ax=ax)
    plt.xticks(rotation=30, ha="right")
    plt.suptitle("")
    ax.set_title("Boxplot per Characteristic")
    st.pyplot(fig)

with c6:
    pareto = stats.copy()
    pareto["OOS"] = pareto["Above OOS"] + pareto["Below OOS"]
    pareto = pareto.sort_values("OOS", ascending=False).head(10)

    pareto["Cum"] = 100 * pareto["OOS"].cumsum() / max(pareto["OOS"].sum(), 1)

    fig, ax1 = plt.subplots(figsize=(7, 4))

    x = range(len(pareto))
    ax1.bar(x, pareto["OOS"], color="#1f77b4")

    ax2 = ax1.twinx()
    ax2.plot(x, pareto["Cum"], color="red", marker="o")
    ax2.axhline(80, linestyle="--")

    ax1.set_xticks(x)
    ax1.set_xticklabels(pareto["Characteristic"], rotation=25, ha="right")

    ax1.set_title("Pareto OOS")

    st.pyplot(fig)
