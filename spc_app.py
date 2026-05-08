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
# AZURE / SHAREPOINT
# =========================
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
TENANT_ID = st.secrets["TENANT_ID"]

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

SCOPES = ["https://graph.microsoft.com/.default"]

# =========================
# AUTHENTICATION
# =========================
app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

token_response = app.acquire_token_for_client(
    scopes=SCOPES
)

# =========================
# ERROR HANDLING
# =========================
if "access_token" not in token_response:

    st.error("Azure authentication failed")
    st.write(token_response)

    st.stop()

access_token = token_response["access_token"]

headers = {
    "Authorization": f"Bearer {access_token}"
}

# =========================
# SHAREPOINT FILES
# =========================
files = {
    "Dataset 0":
    "https://graph.microsoft.com/v1.0/sites/sigitglobal.sharepoint.com:/sites/GQMSpouts131:/drive/root:/Shared%20Documents/Measurements-test%20files/Test-Measurements%26Specs.xlsx:/content",

    "Dataset 1":
    "https://graph.microsoft.com/v1.0/sites/sigitglobal.sharepoint.com:/sites/GQMSpouts131:/drive/root:/Shared%20Documents/Measurements-test%20files/Test-Measurements%26Specs1.xlsx:/content",

    "Dataset 2":
    "https://graph.microsoft.com/v1.0/sites/sigitglobal.sharepoint.com:/sites/GQMSpouts131:/drive/root:/Shared%20Documents/Measurements-test%20files/Test-Measurements%26Specs2.xlsx:/content"
}

# =========================
# DATASET SELECT
# =========================
selected_file = st.sidebar.selectbox(
    "Select dataset",
    list(files.keys())
)

file_url = files[selected_file]

# =========================
# DOWNLOAD FILE
# =========================
response = requests.get(
    file_url,
    headers=headers
)

if response.status_code != 200:

    st.error("Failed loading SharePoint file")
    st.write(response.text)

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

# =========================
# CLEAN COLUMNS
# =========================
df_meas.columns = df_meas.columns.str.strip()
df_specs.columns = df_specs.columns.str.strip()

df_meas["DATE"] = pd.to_datetime(
    df_meas["DATE"]
)

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

# =========================
# RAW MATERIAL FILTER
# =========================
materials = sorted(
    df["RAW MATERIAL"]
    .dropna()
    .unique()
)

if st.sidebar.checkbox(
    "Select all RAW MATERIAL",
    True
):
    selected_m = materials
else:
    selected_m = st.sidebar.multiselect(
        "RAW MATERIAL",
        materials,
        default=materials
    )

df = df[
    df["RAW MATERIAL"]
    .isin(selected_m)
]

# =========================
# COLOR FILTER
# =========================
colors = sorted(
    df["COLOR"]
    .dropna()
    .unique()
)

if st.sidebar.checkbox(
    "Select all COLOR",
    True
):
    selected_c = colors
else:
    selected_c = st.sidebar.multiselect(
        "COLOR",
        colors,
        default=colors
    )

df = df[
    df["COLOR"]
    .isin(selected_c)
]

# =========================
# LIMITS
# =========================
df["USL"] = (
    df["Target"] +
    df["Upper Dev"]
)

df["LSL"] = (
    df["Target"] +
    df["Lower Dev"]
)

# =========================
# STATS
# =========================
g = df.groupby("Characteristic")

stats = pd.DataFrame({
    "Characteristic":
        g["Characteristic"].first(),

    "USL":
        g["USL"].first(),

    "LSL":
        g["LSL"].first(),

    "Mean":
        g["Value"].mean(),

    "Std":
        g["Value"].std(),

    "Max":
        g["Value"].max(),

    "Min":
        g["Value"].min(),

    "Count":
        g["Value"].count()
}).reset_index(drop=True)

# =========================
# CAPABILITY
# =========================
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
above = (
    df[df["Value"] > df["USL"]]
    .groupby("Characteristic")["Value"]
    .count()
)

below = (
    df[df["Value"] < df["LSL"]]
    .groupby("Characteristic")["Value"]
    .count()
)

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
# STYLE
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
    ] = (
        "color:red;"
        "font-weight:bold;"
        "text-decoration:underline"
    )

    s.loc[
        df["Below OOS"] > 0,
        "Below OOS"
    ] = (
        "color:red;"
        "font-weight:bold;"
        "text-decoration:underline"
    )

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

data = df[
    df["Characteristic"] == char
]

spec = stats[
    stats["Characteristic"] == char
].iloc[0]

values = data["Value"].dropna()

# =========================
# ROW 1
# =========================
c1, c2 = st.columns(2)

# CONTROL CHART
with c1:

    fig, ax = plt.subplots(
        figsize=(6, 4)
    )

    ax.plot(
        values.values,
        marker="o",
        color="#005B96",
        linewidth=1.5
    )

    ax.axhline(
        spec["Mean"],
        color="#2ca02c",
        label="Mean"
    )

    ax.axhline(
        spec["USL"],
        color="#d62728",
        linestyle="--",
        label="USL"
    )

    ax.axhline(
        spec["LSL"],
        color="#ff7f0e",
        linestyle="--",
        label="LSL"
    )

    ax.set_title("Control Chart")
    ax.grid(alpha=0.3)

    ax.legend(
        loc="upper right",
        fontsize=8
    )

    plt.tight_layout()

    st.pyplot(fig)

    st.caption(
        "Measurements with specification limits"
    )

# HISTOGRAM
with c2:

    fig, ax = plt.subplots(
        figsize=(6, 4)
    )

    ax.hist(
        values,
        bins=20,
        density=True,
        alpha=0.7,
        color="#6BAED6",
        edgecolor="black"
    )

    if len(values) > 1:

        x = np.linspace(
            values.min(),
            values.max(),
            100
        )

        y = norm.pdf(
            x,
            values.mean(),
            values.std()
        )

        ax.plot(
            x,
            y,
            color="#7A0177",
            linewidth=2
        )

    ax.set_title(
        "Histogram + Normal Curve"
    )

    ax.grid(alpha=0.3)

    plt.tight_layout()

    st.pyplot(fig)

    st.caption(
        "Distribution and fitted normal curve"
    )

# =========================
# ROW 2
# =========================
c3, c4 = st.columns(2)

# I-MR
with c3:

    if len(values) > 1:

        mr = values.diff().abs().dropna()

        fig, ax = plt.subplots(
            2,
            1,
            figsize=(6, 4),
            sharex=True
        )

        ax[0].plot(
            values.values,
            marker="o",
            color="#005B96"
        )

        ax[0].set_title("I Chart")
        ax[0].grid(alpha=0.3)

        ax[1].plot(
            mr.values,
            marker="o",
            color="#FF7F0E"
        )

        ax[1].set_title("Moving Range")
        ax[1].grid(alpha=0.3)

        plt.tight_layout()

        st.pyplot(fig)

        st.caption(
            "Individual values and moving range"
        )

# CAPABILITY
with c4:

    fig, ax = plt.subplots(
        figsize=(6, 4)
    )

    bars = ax.bar(
        ["Cp", "Cpk"],
        [spec["Cp"], spec["Cpk"]],
        color=["#1F77B4", "#17BECF"]
    )

    ax.axhline(
        1.33,
        color="red",
        linestyle="--",
        linewidth=2
    )

    ax.set_title("Capability")

    ax.grid(
        axis="y",
        alpha=0.3
    )

    for bar in bars:

        yval = bar.get_height()

        ax.text(
            bar.get_x() + bar.get_width()/2,
            yval + 0.02,
            round(yval, 2),
            ha="center"
        )

    plt.tight_layout()

    st.pyplot(fig)

    st.caption(
        "Capability evaluation using Cp and Cpk"
    )

# =========================
# GLOBAL OVERVIEW
# =========================
st.markdown(
    "## General overview for selected closure"
)

c5, c6 = st.columns(2)

# BOXPLOT
with c5:

    fig, ax = plt.subplots(
        figsize=(8, 4)
    )

    df.boxplot(
        column="Value",
        by="Characteristic",
        ax=ax,
        grid=False
    )

    plt.xticks(
        rotation=30,
        ha="right"
    )

    plt.suptitle("")

    ax.set_title(
        "Boxplot per Characteristic"
    )

    ax.set_xlabel("")
    ax.set_ylabel("Value")

    plt.tight_layout()

    st.pyplot(fig)

    st.caption(
        "Variation and outliers per characteristic"
    )

# PARETO
with c6:

    pareto = stats.copy()

    pareto["OOS"] = (
        pareto["Above OOS"] +
        pareto["Below OOS"]
    )

    pareto = pareto.sort_values(
        "OOS",
        ascending=False
    ).head(10)

    if pareto["OOS"].sum() > 0:

        pareto["CumPerc"] = (
            100 *
            pareto["OOS"].cumsum() /
            pareto["OOS"].sum()
        )

    else:

        pareto["CumPerc"] = 0

    fig, ax1 = plt.subplots(
        figsize=(8, 4)
    )

    x = range(len(pareto))

    ax1.bar(
        x,
        pareto["OOS"],
        color="#1F77B4"
    )

    labels = [
        l if len(l) < 18
        else l[:15] + "..."
        for l in pareto["Characteristic"]
    ]

    ax1.set_xticks(x)

    ax1.set_xticklabels(
        labels,
        rotation=20,
        ha="right"
    )

    ax1.set_ylabel(
        "OOS Count"
    )

    ax1.grid(
        axis="y",
        alpha=0.3
    )

    ax2 = ax1.twinx()

    ax2.plot(
        x,
        pareto["CumPerc"],
        color="#D62728",
        marker="o",
        linewidth=2
    )

    ax2.axhline(
        80,
        color="#FF7F0E",
        linestyle="--"
    )

    ax2.set_ylabel(
        "Cumulative %"
    )

    ax1.set_title(
        "Pareto OOS Analysis"
    )

    plt.tight_layout()

    st.pyplot(fig)

    st.caption(
        "Bars = OOS count | Line = cumulative percentage"
    )
