"""Streamlit composition root. No historical integrations or package mutation."""

import streamlit as st

from outreach.ui import run

st.set_page_config(page_title="Mass Outreach", page_icon="✉️", layout="wide")
run()
