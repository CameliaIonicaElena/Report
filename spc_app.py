import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from msal import ConfidentialClientApplication
import requests
from io import BytesIO

# =========================================================
# PAGE CONFIG
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

    pwd = st.text_input(
        "Enter password - Ask any GQM team member for extra info",
        type="password"
    )

    if st.button("Login"):

        if pwd == PASSWORD:
            st.session_state.auth = True
            st.success("Access granted")
            st.rerun()

        else:
            st.error("Wrong password")

# =========================================================
# SOURCES CONFIG (FIXED)
# =========================================================
sites = {
    "ALPLA Hefei": {
        "site_id": "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Hefei:",
        "folder": "Measurements-test files"
    },
    "ALPLA Brazil": {
        "site_id": "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Brazil:",
        "folder": "Measurements-test files"
    },
    "ALPLA Waidhofen": {
        "site_id": "sigitglobal.sharepoint.com:/sites/GLB-Quality-Alpla_Waidhofen:",
        "folder": "Measurements-test files"
    }
}

# =========================================================
# SAFE ACCESS FUNCTION
# =========================================================
def get_site_config(site_name):
    config = sites.get(site_name)

    if config is None:
        st.error(f"Site '{site_name}' not found in configuration")
        return None, None

    site_id = config.get("site_id")
    folder = config.get("folder")

    if not site_id or not folder:
        st.error(f"Incomplete config for {site_name}")
        return None, None

    return site_id, folder

# =========================================================
# PLACEHOLDER FOR YOUR SHAREPOINT LOGIC
# =========================================================
def search_folder(site_id, folder):
    """
    AICI ai logica ta reală de SharePoint / API.
    Am lăsat placeholder ca să nu îți stric structura.
    """
    try:
        # EXAMPLE REQUEST (adaptat de tine)
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{folder}:/children"

        headers = {
            "Authorization": "Bearer YOUR_TOKEN"
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()

        return None

    except Exception as e:
        st.error(f"Folder search error: {e}")
        return None

# =========================================================
# UI EXAMPLE FLOW
# (asta e partea care probabil o ai deja în codul real)
# =========================================================
if st.session_state.auth:

    selected_site = st.selectbox("Select site", list(sites.keys()))

    site_id, folder = get_site_config(selected_site)

    if site_id and folder:

        st.write("Selected site:", selected_site)
        st.write("Site ID:", site_id)
        st.write("Folder:", folder)

        result = search_folder(site_id, folder)

        if not result:
            st.error("Folder search failed")
        else:
            st.success("Folder found / data loaded")
