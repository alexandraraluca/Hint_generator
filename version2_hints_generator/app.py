from __future__ import annotations

import streamlit as st

from config import N_HINTS
from data_loader import load_problems, submissions_for_problem
from feedback_store import (
    append_feedback,
    append_preference_pairs,
    load_feedback_count,
    load_pairs_count,
)
from llm_client import generate_candidate_hints
from prompting import build_hint_prompt
from reward_data import build_preference_pairs, build_scored_hints


def _display_value(value: object) -> str:
    text = str(value or "").strip()
    if text in {"", "?", "null", "None"}:
        return "N/A"
    return text


st.set_page_config(page_title="Version2 Hints Generator", layout="wide")
st.title("Version2 Hints Generator")

problems = load_problems()
problem_ids = sorted(problems.keys())

left, middle = st.columns([1.15, 1.85])

with left:
    selected_problem_id = st.selectbox("Choose exercise:", problem_ids)
    problem = problems[selected_problem_id]
    st.subheader(f"Exercise: {problem.name or selected_problem_id}")
    st.markdown(problem.statement or "_No statement available_")

    problem_submissions = submissions_for_problem(selected_problem_id)
    submission_map = {f"{s.submission_id} ({s.verdict})": s for s in problem_submissions[:200]}
    selected_submission_label = st.selectbox(
        "Choose student submission:",
        options=list(submission_map.keys()) if submission_map else ["Manual code only"],
    )
    selected_submission = submission_map.get(selected_submission_label)
    test_data = selected_submission.test if selected_submission else None

    st.markdown("### Failed test details")
    if test_data:
        st.caption(f"Verdict: {selected_submission.verdict}")
        st.text_area(
            "Checker comment",
            value=_display_value(test_data.get("checker_comment")),
            height=80,
            disabled=True,
        )
        st.text_area(
            "Input (failed test)",
            value=_display_value(test_data.get("input")),
            height=120,
            disabled=True,
        )
        st.text_area(
            "Expected output",
            value=_display_value(test_data.get("jury_answer")),
            height=90,
            disabled=True,
        )
        st.text_area(
            "Student output",
            value=_display_value(test_data.get("participant_output")),
            height=90,
            disabled=True,
        )
    else:
        st.caption("No failed test data available for this submission.")

with middle:
    default_code = selected_submission.code if selected_submission else ""
    code = st.text_area("Student code", value=default_code, height=360)
    generate = st.button("Generate 3 hints")

    if generate:
        verdict = selected_submission.verdict if selected_submission else "UNKNOWN"
        prompt_text, prompt_json = build_hint_prompt(
            statement=problem.statement or "",
            student_code=code,
            verdict=verdict,
            test_data=test_data,
            n_hints=N_HINTS,
        )
        candidates = generate_candidate_hints(prompt=prompt_text, verdict=verdict)

        # Ensure exactly 3 hint slots.
        candidates = (candidates + [""] * N_HINTS)[:N_HINTS]

        st.session_state["generated_hints"] = candidates
        st.session_state["prompt_json"] = prompt_json
        st.session_state["selected_problem_id"] = selected_problem_id
        st.session_state["selected_submission_id"] = (
            selected_submission.submission_id if selected_submission else None
        )

    hints: list[str] = st.session_state.get("generated_hints", [])
    if hints:
        st.success("Rate each hint individually")
        with st.form("hint_feedback_form"):
            feedback_items = []
            for idx, hint in enumerate(hints, start=1):
                st.markdown(f"### Hint {idx}")
                st.markdown(hint or "_No hint generated_")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    clarity = st.slider(f"clarity_{idx}", 1, 5, 3, key=f"clarity_{idx}")
                with c2:
                    usefulness = st.slider(
                        f"usefulness_{idx}", 1, 5, 3, key=f"usefulness_{idx}"
                    )
                with c3:
                    relevance = st.slider(f"relevance_{idx}", 1, 5, 3, key=f"relevance_{idx}")
                with c4:
                    too_revealing = st.slider(
                        f"too_revealing_{idx}", 1, 5, 1, key=f"too_revealing_{idx}"
                    )
                feedback_items.append(
                    {
                        "hint": hint,
                        "clarity": clarity,
                        "usefulness": usefulness,
                        "relevance": relevance,
                        "too_revealing": too_revealing,
                    }
                )

            comment = st.text_area("Other comments (optional)")
            submitted = st.form_submit_button("Submit feedback and build preference pairs")

            if submitted:
                scored_hints = build_scored_hints(feedback_items)
                pairs = build_preference_pairs(
                    prompt_json=st.session_state.get("prompt_json", "{}"),
                    scored_hints=scored_hints,
                )

                feedback_payload = {
                    "problem_id": st.session_state.get("selected_problem_id"),
                    "submission_id": st.session_state.get("selected_submission_id"),
                    "prompt": st.session_state.get("prompt_json", "{}"),
                    "comment": comment,
                    "hints": [
                        {
                            "hint": item.hint,
                            "clarity": item.clarity,
                            "usefulness": item.usefulness,
                            "relevance": item.relevance,
                            "too_revealing": item.too_revealing,
                            "penalty": round(item.penalty, 4),
                            "score": round(item.score, 4),
                        }
                        for item in scored_hints
                    ],
                }

                append_feedback(feedback_payload)
                append_preference_pairs(pairs)

                st.success(
                    f"Saved. Feedback entries: {load_feedback_count()} | Preference pairs: {load_pairs_count()}"
                )
                if not pairs:
                    st.warning(
                        "No preference pairs were produced (scores might be tied). Try clearer rating gaps."
                    )
                else:
                    st.json(pairs)
