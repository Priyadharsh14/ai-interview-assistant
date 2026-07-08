"""
Collection Name Registry.

Centralised helpers for building consistent ChromaDB collection names.

Why this matters:
- Collection names must be unique per document to avoid cross-contamination
- Resumeuser A's resume must not pollute user B's search results
- A session-scoped naming strategy isolates each upload cleanly

Strategy:
    resume_{session_id}      — chunks from a specific resume upload
    jd_{session_id}          — chunks from a specific JD upload

In a multi-user production deployment the session_id would be the user's
account ID. In the current Streamlit single-user deployment it is the
Streamlit session ID from st.session_state.
"""

from __future__ import annotations

import re


def resume_collection(session_id: str) -> str:
    """
    Return the ChromaDB collection name for a resume.

    Args:
        session_id: User or session identifier.

    Returns:
        Collection name string safe for ChromaDB.
    """
    return f"resume_{_sanitize(session_id)}"


def jd_collection(session_id: str) -> str:
    """
    Return the ChromaDB collection name for a job description.

    Args:
        session_id: User or session identifier.

    Returns:
        Collection name string safe for ChromaDB.
    """
    return f"jd_{_sanitize(session_id)}"


def _sanitize(value: str) -> str:
    """
    Make a string safe for use as a ChromaDB collection name.

    ChromaDB collection names:
    - Must be 3-63 characters
    - Must start and end with alphanumeric characters
    - Can contain hyphens and underscores in the middle
    - Cannot contain consecutive periods

    Args:
        value: Raw identifier string.

    Returns:
        Sanitised collection name component.
    """
    # Replace non-alphanumeric (except hyphens) with underscores
    clean = re.sub(r"[^a-zA-Z0-9\-]", "_", value)
    # Truncate to keep total name within 63 chars (prefix adds ~3 chars)
    return clean[:55]
