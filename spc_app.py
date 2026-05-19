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
# ACCESS PASSWORD GATE
# =========================================================
PASSWORD = "ShowRepoGQM31" 

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:

    st.subheader("Confidential Data - Access Required")

    pwd = st.text_input("Enter password - Ask any GQM team memnber for extra info", type="password")

    if st.button("Login"):

        if pwd == PASSWORD:
            st.session_state.auth = True
            st.success("Access granted")
            st.rerun()


# =========================================================
# SOURCES (FIXED SECTION)
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

# SAFE ACCESS HELPER
def get_site_config(site_name):
    config = sites.get(site_name)

    if not config:
        st.error(f"Site not found: {site_name}")
        return None, None

    site_id = config.get("site_id")
    folder = config.get("folder")

    if not site_id or not folder:
        st.error(f"Incomplete configuration for {site_name}")
        return None, None

    return site_id, folder


# =========================================================
# EXAMPLE USAGE (where your folder search happens)
# =========================================================
# selected_site = st.selectbox("Select site", list(sites.keys()))
#
# site_id, folder = get_site_config(selected_site)
#
# if site_id and folder:
#     result = search_folder(site_id, folder)
#     if not result:
#         st.error("Folder search failed")
