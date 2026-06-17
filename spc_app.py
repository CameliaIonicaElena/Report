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
# AUTH
# =========================================================
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
TENANT_ID = st.secrets["TENANT_ID"]

app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    client_credential=CLIENT_SECRET
)

token = app.acquire_token_for_client(
    scopes=["https://graph.microsoft.com/.default"]
)

if "access_token" not in token:
    st.error("Auth failed")
    st.stop()

headers = {"Authorization": f"Bearer {token['access_token']}"}

# =========================================================
# UI STYLES
# =========================================================
def blue_title(text, size=28):
    st.markdown(
        f"<h1 style='color:#A7C7E7; font-size:{size}px; font-weight:700;'>{text}</h1>",
        unsafe_allow_html=True
    )

def section_title(text):
    st.markdown(
        f"<h2 style='color:#A7C7E7; font-weight:600;'>{text}</h2>",
        unsafe_allow_html=True
    )

# =========================================================
# SITES
# =========================================================
sites = {
    "ALPLA Hefei": "/sites/GLB-Quality-Alpla_Hefei",
    "ALPLA Brazil": "/sites/GLB-Quality-Alpla_Brazil",
    "ALPLA Waidhofen": "/sites/GLB-Quality-Alpla_Waidhofen",
    "ALPLA Spain": "/sites/EU-Quality-Alpla_Spain",
    "ALPLA Thailand": "/sites/GLB-Quality-Alpla_Thailand",
    "ALPLA Mexico": "/sites/GLB-Quality-Alpla_Mexico",
    "JABIL Spain": "/sites/GLB-Quality-Jabil_Spain",
    "JABIL Hungary": "/sites/GLB-Quality-Jabil_Hungary",
    "BERICAP": "/sites/BERICAP",
    "Obeikan": "/sites/ORP_-_Obeikan",
    "PNE": "/sites/SIG_PNE",
    "Scholle": "/sites/Scholle_IPN",
    "Vinhedo": "/sites/GLB-Quality-SIG-Vinhedo",
    "Peachtree": "/sites/GLB-Quality-SIG-Peachtree"
}

site_name = st.sidebar.selectbox("Site", list(sites.keys()))
site_path = sites[site_name]

# =========================================================
# SITE ID
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
# SAFE PATH NAVIGATION
# =========================================================
def list_folder(path):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/{path}:/children"
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        return []

    return r.json().get("value", [])

BASE = "Quality Files Exchange"
YEAR = "2026"

# =========================================================
# YEAR
# =========================================================
year_items = list_folder(BASE)
year_folder = next((x for x in year_items if x["name"] == YEAR), None)

if not year_folder:
    st.error("2026 not found")
    st.stop()

# =========================================================
# LINE
# =========================================================
lines = list_folder(f"{BASE}/{YEAR}")
lines = [x for x in lines if "folder" in x]

selected_line = st.sidebar.selectbox(
    "Line",
    [l["name"] for l in lines]
)

LINE = selected_line

# =========================================================
# FILES
# =========================================================
files = {
    "Cap": "Cap-Measurements&Specs.xlsx",
    "Flange": "Flange-Measurements&Specs.xlsx",
    "Cutting Ring": "Cutting-Ring-Measurements&Specs.xlsx"
}

dataset = st.sidebar.selectbox("Dataset", list(files.keys()))
file_name = files[dataset]

file_path = f"{BASE}/{YEAR}/{LINE}/{file_name}"

# =========================================================
# DOWNLOAD FILE
# =========================================================
def download_file(path):
    url = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/{path}:/content"
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        return None

    return BytesIO(r.content)

excel = download_file(file_path)

if excel is None:
    st.error("File not found")
    st.stop()

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
start, end = st.sidebar.date_input(
    "Date range",
    value=(df["DATE"].min(), df["DATE"].max())
)

df = df[
    (df["DATE"] >= pd.to_datetime(start)) &
    (df["DATE"] <= pd.to_datetime(end))
]

materials = sorted(df["RAW MATERIAL"].dropna().unique())
colors = sorted(df["COLOR"].dropna().unique())

df = df[
    df["RAW MATERIAL"].isin(
        st.sidebar.multiselect(
            "Material",
            materials,
            default=materials
        )
    ) &
    df["COLOR"].isin(
        st.sidebar.multiselect(
            "Color",
            colors,
            default=colors
        )
    )
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

# =========================================================
# OOS
# =========================================================
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
# STYLE TABLE
# =========================================================
def style(df):
    s = pd.DataFrame("", index=df.index, columns=df.columns)

    s.loc[
        df["Above OOS"] > 0,
        "Above OOS"
    ] = "color:red;font-weight:bold"

    s.loc[
        df["Below OOS"] > 0,
        "Below OOS"
    ] = "color:red;font-weight:bold"

    s.loc[
        df["Process Capability"] == "Excellent",
        "Process Capability"
    ] = "color:green;font-weight:bold"

    s.loc[
        df["Process Capability"] == "Capable",
        "Process Capability"
    ] = "color:goldenrod;font-weight:bold"

    s.loc[
        df["Process Capability"] == "Marginal",
        "Process Capability"
    ] = "color:orange;font-weight:bold"

    s.loc[
        df["Process Capability"] == "Not capable",
        "Process Capability"
    ] = "color:red;font-weight:bold"

    return s

# =========================================================
# OVERVIEW BUTTON
# =========================================================
st.sidebar.markdown("---")

show_overview = st.sidebar.button("Show OOS Overview")

if show_overview:

    overview_rows = []

    all_lines = list_folder(f"{BASE}/{YEAR}")
    all_lines = [x for x in all_lines if "folder" in x]

    for line in all_lines:

        line_name = line["name"]

        for dataset_name, dataset_file in files.items():

            try:

                current_path = (
                    f"{BASE}/{YEAR}/{line_name}/{dataset_file}"
                )

                overview_excel = download_file(current_path)

                if overview_excel is None:
                    continue

                ov_meas = pd.read_excel(
                    overview_excel,
                    sheet_name="Measurements"
                )

                overview_excel.seek(0)

                ov_specs = pd.read_excel(
                    overview_excel,
                    sheet_name="Specs"
                )

                ov_meas.columns = ov_meas.columns.str.strip()
                ov_specs.columns = ov_specs.columns.str.strip()

                ov_meas["DATE"] = pd.to_datetime(
                    ov_meas["DATE"]
                )

                ov_long = ov_meas.melt(
                    id_vars=[
                        "DATE",
                        "RAW MATERIAL",
                        "COLOR",
                        "CAV"
                    ],
                    var_name="Characteristic",
                    value_name="Value"
                )

                ov_df = ov_long.merge(
                    ov_specs,
                    on="Characteristic",
                    how="left"
                )

                ov_df["USL"] = (
                    ov_df["Target"] +
                    ov_df["Upper Dev"]
                )

                ov_df["LSL"] = (
                    ov_df["Target"] +
                    ov_df["Lower Dev"]
                )

                oos_df = ov_df[
                    (ov_df["Value"] > ov_df["USL"]) |
                    (ov_df["Value"] < ov_df["LSL"])
                ]

                if not oos_df.empty:

                    oos_summary = (
                        oos_df.groupby("Characteristic")
                        .size()
                        .reset_index(name="OOS Count")
                    )

                    oos_summary["Line"] = line_name
                    oos_summary["Dataset"] = dataset_name

                    overview_rows.append(oos_summary)

            except:
                pass

    section_title("Out Of Spec Overview")

    if overview_rows:

        final_overview = pd.concat(
            overview_rows,
            ignore_index=True
        )

        final_overview = final_overview[
            [
                "Line",
                "Dataset",
                "Characteristic",
                "OOS Count"
            ]
        ]

        final_overview = final_overview.sort_values(
            by="OOS Count",
            ascending=False
        )

        st.dataframe(
            final_overview,
            use_container_width=True
        )

    else:
        st.success("No Out Of Spec values found")

# =========================================================
# UI HEADER
# =========================================================
section_title("SPC Summary")

st.dataframe(
    stats.style.apply(style, axis=None),
    use_container_width=True
)

st.markdown(
    "<h2 style='color:#A7C7E7; font-size:30px;'>Please select one Measurement Point</h2>",
    unsafe_allow_html=True
)

char = st.selectbox(
    "",
    stats["Characteristic"]
)

data = df[df["Characteristic"] == char]

filtered_spec = stats[
    stats["Characteristic"] == char
]

if filtered_spec.empty:
    st.error(f"No specification found for '{char}'")
    st.stop()

spec = filtered_spec.iloc[0]

values = data["Value"].dropna()

# =========================================================
# CHARTS
# =========================================================
col1, col2 = st.columns(2)

with col1:

    st.markdown("### Trend Chart")

    fig, ax = plt.subplots()

    ax.plot(
        values.values,
        label="Values",
        color="blue"
    )

    ax.axhline(
        spec["Mean"],
        label="Mean",
        color="purple"
    )

    ax.axhline(
        spec["USL"],
        linestyle="--",
        label="USL",
        color="red"
    )

    ax.axhline(
        spec["LSL"],
        linestyle="--",
        label="LSL",
        color="red"
    )

    ax.set_title(f"Trend - {char}")

    ax.grid()

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.2),
        ncol=2
    )

    st.pyplot(fig)

with col2:

    st.markdown("### Distribution")

    fig, ax = plt.subplots()

    ax.hist(
        values,
        bins=20,
        density=True,
        alpha=0.6,
        color="#A7C7E7"
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

    ax.set_title(f"Distribution - {char}")

    ax.grid()

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.2)
    )

    st.pyplot(fig)
