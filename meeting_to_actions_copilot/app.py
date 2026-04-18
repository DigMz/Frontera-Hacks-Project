from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from extract import extract_pain_points, map_pain_points, to_csv_bytes, to_markdown
from llm import extract_with_llm_with_raw


st.set_page_config(page_title="Meeting-to-Actions Copilot", layout="wide")

st.title("Meeting-to-Actions Copilot")

with st.sidebar:
    st.subheader("Settings")
    model = st.text_input("Model", value="claude-3-5-sonnet-latest")
    show_raw = st.checkbox("Show raw model output", value=False)
    run = st.button("Run extraction", type="primary")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Meeting notes")
    text = st.text_area(
        "Paste transcript/notes",
        height=420,
        placeholder="Paste your meeting transcript or notes here...",
        label_visibility="collapsed",
    )

with col2:
    st.subheader("Output")
    placeholder = st.empty()

if run:
    if not text.strip():
        st.warning("Paste meeting notes first.")
    else:
        started = time.time()
        with st.spinner("Extracting..."):
            out, raw = extract_with_llm_with_raw(text=text, model=model.strip() or "claude-3-5-sonnet-latest")
        elapsed = time.time() - started

        md = to_markdown(out)
        pain_points = extract_pain_points(text)
        mappings = map_pain_points(pain_points=pain_points, decisions=out.decisions, action_items=out.action_items)

        with placeholder.container():
            st.caption(f"Done in {elapsed:.2f}s")

            st.markdown("### AI Summary")
            if out.summary:
                for s in out.summary:
                    st.write(f"- {s}")
            else:
                st.write("(none)")

            st.markdown("### Key Decisions")
            if out.decisions:
                for d in out.decisions:
                    st.write(f"- {d}")
            else:
                st.write("(none)")

            st.markdown("### Action items")
            if out.action_items:
                df = pd.DataFrame(
                    [
                        {
                            "task": a.task,
                            "owner": a.owner,
                            "due_date": a.due_date,
                            "priority": a.priority,
                            "urgency": "High Priority" if (a.priority or "").upper() == "P1" else "",
                        }
                        for a in out.action_items
                    ]
                )
                def _highlight_p1(row):
                    if str(row.get("priority", "")).upper() == "P1":
                        return ["background-color: #6a4f00; color: #ffffff; font-weight: 600"] * len(row)
                    return [""] * len(row)

                styled = df.style.apply(_highlight_p1, axis=1)

                st.dataframe(styled, use_container_width=True, hide_index=True)
            else:
                st.write("(none)")

            st.markdown("### Pain point → decision → action")
            if mappings:
                for m in mappings:
                    st.markdown(f"**Pain point:** {m['pain_point']}")
                    if m["decisions"]:
                        st.write("Decisions")
                        for d in m["decisions"]:
                            st.write(f"- {d}")
                    else:
                        st.write("Decisions")
                        st.write("- (none)")

                    if m["actions"]:
                        st.write("Actions")
                        for a in m["actions"]:
                            st.write(f"- {a.task} ({a.owner})")
                    else:
                        st.write("Actions")
                        st.write("- (none)")
            else:
                st.write("(none)")

            st.download_button(
                "Download Markdown",
                data=md.encode("utf-8"),
                file_name="meeting_output.md",
                mime="text/markdown",
            )
            st.download_button(
                "Download CSV",
                data=to_csv_bytes(out),
                file_name="action_items.csv",
                mime="text/csv",
            )

            if show_raw and raw.strip():
                st.markdown("### Raw model output")
                st.code(raw, language="text")

st.divider()

st.markdown("#### Quick demo notes")

st.code(
    """Decision: We will ship v1 on Friday.
Action: Ei Ei to draft the announcement email by Thursday.
Action: Alex to update the onboarding doc by 2026-04-20 (priority P2).
Follow up: confirm budget approval with finance.""",
    language="text",
)
