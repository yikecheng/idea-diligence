"""Public Streamlit entry point with separate temporary data for each visitor."""

from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st

from app import main
from idea_diligence.storage import use_visitor_database


if "visitor_workspace" not in st.session_state:
    st.session_state.visitor_workspace = TemporaryDirectory(prefix="idea-diligence-")

with use_visitor_database(Path(st.session_state.visitor_workspace.name) / "workspace.sqlite3"):
    main()
