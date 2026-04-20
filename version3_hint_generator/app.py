from __future__ import annotations

import html
import re
from typing import Any

import streamlit as st

from concept_dag import extract_concepts, get_concept_by_id, topological_sort
from config import N_HINTS
from data_loader import load_problems, submissions_for_problem
from feedback_store import (
    append_feedback,
    append_preference_pairs,
    load_feedback_count,
    load_pairs_count,
)
from llm_client import ollama_chat, parse_json_response
from models import Concept, Submission
from prompting import (
    build_code_analysis_prompt,
    build_general_hint_prompt,
    build_specific_hint_prompt,
)
from reward_data import build_feedback_items, build_preference_pairs

# ─── Display helpers ─────────────────────────────────────────────────────────


def _display_value(value: object) -> str:
    text = str(value or "").strip()
    return "N/A" if text in {"", "?", "null", "None"} else text


def _normalize_statement(value: object) -> str:
    text = str(value or "").replace("\r\n", "\n").strip()
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines()]
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return re.sub(r"[ \t]+", " ", "\n\n".join(paragraphs)).strip()


def _render_statement(statement: object) -> None:
    normalized = _normalize_statement(statement)
    if not normalized:
        st.markdown("_No statement available_")
        return
    safe = html.escape(normalized).replace("\n\n", "<br><br>")
    st.markdown(
        f"<div style='font-size:1rem;line-height:1.6'>{safe}</div>",
        unsafe_allow_html=True,
    )


# ─── Session-state helpers ────────────────────────────────────────────────────


def _reset_flow() -> None:
    """Clear all hint-flow keys from session state."""
    for key in [
        "hint_mode",
        "phase",
        "concepts",
        "topo_order",
        "question_idx",
        "understood_ids",
        "missing_concept",
        "analysis_reason",
        "student_code_snapshot",
        "selected_submission_key",
        "generated_hints",
        "hint_prompt_json",
        "feedback_submitted",
        "_last_pairs",
        "_last_fb_count",
        "_last_pairs_count",
    ]:
        st.session_state.pop(key, None)


def _ss(key: str, default: Any = None) -> Any:
    return st.session_state.get(key, default)


# ─── Hint generation helpers ─────────────────────────────────────────────────


def _call_hint_llm_general(problem: Any, concept: Concept) -> tuple[list[str], str]:
    solution = problem.tutorial.solution or ""
    if not solution and problem.tutorial.hints:
        solution = " ".join(problem.tutorial.hints)

    prompt_text, prompt_json = build_general_hint_prompt(
        statement=problem.statement or "",
        solution=solution,
        concept=concept,
    )
    raw = ollama_chat(
        user_prompt=prompt_text,
        system_prompt='Return only valid JSON. Schema: {"hints":["hint1","hint2"]}.',
        temperature=0.6,
    )
    data = parse_json_response(raw)
    raw_hints = data.get("hints", [])
    hints = [str(h).strip() for h in raw_hints if h][:N_HINTS]
    hints = (hints + [""] * N_HINTS)[:N_HINTS]
    return hints, prompt_json


def _call_hint_llm_specific(
    problem: Any,
    submission: Submission | None,
    student_code: str,
    concept: Concept,
    reason: str,
) -> tuple[list[str], str]:
    solution = problem.tutorial.solution or ""
    test_data = submission.test if submission else None
    verdict = submission.verdict if submission else "UNKNOWN"

    prompt_text, prompt_json = build_specific_hint_prompt(
        statement=problem.statement or "",
        solution_text=solution,
        solution_code=problem.tutorial.code,
        student_code=student_code,
        test_data=test_data,
        verdict=verdict,
        concept=concept,
        analysis_reason=reason,
    )
    raw = ollama_chat(
        user_prompt=prompt_text,
        system_prompt='Return only valid JSON. Schema: {"hints":["hint1","hint2"]}.',
        temperature=0.6,
    )
    data = parse_json_response(raw)
    raw_hints = data.get("hints", [])
    hints = [str(h).strip() for h in raw_hints if h][:N_HINTS]
    hints = (hints + [""] * N_HINTS)[:N_HINTS]
    return hints, prompt_json


# ─── Rating section (rendered inline in the right column) ────────────────────


def _render_rating_section(problem_id: str, submission: Submission | None, mode: str) -> None:
    hints: list[str] = _ss("generated_hints", [])
    missing_concept: Concept | None = _ss("missing_concept")

    if not any(h.strip() for h in hints):
        st.warning("No hints were generated. Please try again.")
        if st.button("← Back", key="back_from_empty"):
            st.session_state["phase"] = "questioning" if mode == "general" else "idle"
            st.rerun()
        return

    concept_label = missing_concept.name if missing_concept else "concept"
    st.markdown(f"### Hints for: **{concept_label}**")
    st.caption("Rate each hint — this feedback trains the reward model.")

    # ── Show rating form only if feedback not yet submitted in this round ─────
    if not _ss("feedback_submitted"):
        with st.form("hint_feedback_form_v3"):
            ratings: dict[int, str] = {}
            for idx, hint in enumerate(hints):
                if not hint.strip():
                    continue
                st.markdown(f"#### Hint {idx + 1}")
                st.markdown(hint)
                choice = st.radio(
                    f"Rate hint {idx + 1}",
                    options=["ok", "not ok"],
                    horizontal=True,
                    key=f"rate_{idx}",
                    label_visibility="collapsed",
                )
                ratings[idx] = "ok" if choice == "ok" else "not_ok"

            comment = st.text_area("Other comments (optional)", key="feedback_comment")
            submitted = st.form_submit_button("Submit feedback & build preference pairs")

            if submitted:
                feedback_items = build_feedback_items(hints, ratings)
                prompt_json = _ss("hint_prompt_json", "{}")
                pairs = build_preference_pairs(prompt_json, feedback_items)

                sub_id = submission.submission_id if submission else None
                feedback_payload = {
                    "problem_id": problem_id,
                    "submission_id": sub_id,
                    "mode": mode,
                    "missing_concept": (
                        {"id": missing_concept.id, "name": missing_concept.name}
                        if missing_concept
                        else None
                    ),
                    "prompt": prompt_json,
                    "comment": comment,
                    "hints": [
                        {"hint": f.hint, "rating": f.rating, "score": f.score}
                        for f in feedback_items
                    ],
                }

                append_feedback(feedback_payload)
                append_preference_pairs(pairs)

                # Store results and flag so navigation buttons appear outside the form
                st.session_state["feedback_submitted"] = True
                st.session_state["_last_pairs"] = pairs
                st.session_state["_last_fb_count"] = load_feedback_count()
                st.session_state["_last_pairs_count"] = load_pairs_count()
                st.rerun()

    # ── Post-submit: show results + navigation buttons (outside any form) ─────
    else:
        pairs = _ss("_last_pairs", [])
        fb_count = _ss("_last_fb_count", 0)
        pairs_count = _ss("_last_pairs_count", 0)

        st.success(f"Saved. Feedback entries: {fb_count} | Preference pairs: {pairs_count}")
        if pairs:
            st.json(pairs)
        else:
            st.info(
                "No preference pairs produced — need at least one 'ok' "
                "and one 'not ok' rating."
            )

        st.markdown("---")

        if mode == "general":
            concepts: list[Concept] = _ss("concepts", [])
            topo_order: list[str] = _ss("topo_order", [])
            next_idx: int = _ss("question_idx", 0) + 1  # concept after the one just hinted

            if next_idx <= len(topo_order):
                next_cid = topo_order[next_idx - 1] if next_idx <= len(topo_order) else None
                # peek at the upcoming concept name for the button label
                upcoming = get_concept_by_id(concepts, topo_order[next_idx]) if next_idx < len(topo_order) else None
                if upcoming:
                    next_btn_label = f"➡️  Continue — next concept: **{upcoming.name}**"
                else:
                    next_btn_label = "✅  Continue — all concepts covered"
            else:
                next_btn_label = "✅  Continue"

            nav_col1, nav_col2 = st.columns(2)
            with nav_col1:
                if st.button(next_btn_label, use_container_width=True, key="continue_next_concept"):
                    # Advance past the concept that was just hinted
                    st.session_state["question_idx"] = next_idx
                    # Clear round-specific keys
                    for k in ("feedback_submitted", "generated_hints", "missing_concept",
                              "hint_prompt_json", "_last_pairs", "_last_fb_count", "_last_pairs_count"):
                        st.session_state.pop(k, None)
                    st.session_state["phase"] = "questioning"
                    st.rerun()
            with nav_col2:
                if st.button("🔄  Restart from scratch", use_container_width=True, key="restart_general"):
                    _reset_flow()
                    st.session_state["current_problem_id"] = problem_id
                    st.session_state["hint_mode"] = "general"
                    st.session_state["phase"] = "extracting"
                    st.rerun()

        else:  # specific mode
            if st.button("🔄  Analyze another submission", use_container_width=True, key="analyze_another"):
                for k in ("feedback_submitted", "generated_hints", "missing_concept",
                          "hint_prompt_json", "_last_pairs", "_last_fb_count", "_last_pairs_count"):
                    st.session_state.pop(k, None)
                st.session_state["phase"] = "idle"
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE SETUP
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="Version3 Hints Generator", layout="wide")
st.title("Version3 Hints Generator — Concept-Guided")

problems = load_problems()
problem_ids = sorted(problems.keys())

# ─── Initialise cross-column variables ───────────────────────────────────────
selected_submission: Submission | None = None
test_data: dict[str, Any] | None = None

left, right = st.columns([1.2, 1.8])

# ═══════════════════════════════════════════════════════════════════════════════
# LEFT COLUMN
# ═══════════════════════════════════════════════════════════════════════════════
with left:
    selected_problem_id: str = st.selectbox("Choose exercise:", problem_ids)

    # Reset everything when the user picks a different problem
    if _ss("current_problem_id") != selected_problem_id:
        _reset_flow()
        st.session_state["current_problem_id"] = selected_problem_id

    problem = problems[selected_problem_id]
    st.subheader(f"Exercise: {problem.name or selected_problem_id}")
    _render_statement(problem.statement)

    # Submission selector — only relevant for Specific Hints mode
    if _ss("hint_mode") == "specific":
        st.markdown("---")
        problem_subs = submissions_for_problem(selected_problem_id)
        # Prefer failed submissions for specific hints; fall back to all
        failed_subs = [s for s in problem_subs if s.verdict.upper() != "ACCEPTED"]
        display_subs = (failed_subs or problem_subs)[:150]

        sub_map: dict[str, Submission] = {
            f"{s.submission_id} ({s.verdict})": s for s in display_subs
        }

        if sub_map:
            chosen_label = st.selectbox(
                "Choose student submission:",
                options=list(sub_map.keys()),
                key="submission_selector",
            )
            selected_submission = sub_map[chosen_label]
            test_data = selected_submission.test

            st.markdown("### Failed test details")
            if test_data:
                st.caption(f"Verdict: {selected_submission.verdict}")
                st.text_area(
                    "Checker comment",
                    value=_display_value(test_data.get("checker_comment")),
                    height=60,
                    disabled=True,
                    key="tc_checker",
                )
                st.text_area(
                    "Input (failed test)",
                    value=_display_value(test_data.get("input")),
                    height=100,
                    disabled=True,
                    key="tc_input",
                )
                st.text_area(
                    "Expected output",
                    value=_display_value(test_data.get("jury_answer")),
                    height=70,
                    disabled=True,
                    key="tc_expected",
                )
                st.text_area(
                    "Student output",
                    value=_display_value(test_data.get("participant_output")),
                    height=70,
                    disabled=True,
                    key="tc_output",
                )
            else:
                st.caption("No failed test data for this submission.")
        else:
            st.info("No submissions found for this problem.")

# ═══════════════════════════════════════════════════════════════════════════════
# RIGHT COLUMN
# ═══════════════════════════════════════════════════════════════════════════════
with right:

    # ── Mode selection ────────────────────────────────────────────────────────
    hint_mode: str | None = _ss("hint_mode")
    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        general_type = "primary" if hint_mode == "general" else "secondary"
        if st.button("General Hints", use_container_width=True, type=general_type):
            _reset_flow()
            st.session_state["current_problem_id"] = selected_problem_id
            st.session_state["hint_mode"] = "general"
            st.session_state["phase"] = "extracting"
            st.rerun()

    with btn_col2:
        specific_type = "primary" if hint_mode == "specific" else "secondary"
        if st.button("Specific Hints", use_container_width=True, type=specific_type):
            _reset_flow()
            st.session_state["current_problem_id"] = selected_problem_id
            st.session_state["hint_mode"] = "specific"
            st.session_state["phase"] = "idle"
            st.rerun()

    st.markdown("---")

    # Refresh after potential button click
    hint_mode = _ss("hint_mode")
    phase: str = _ss("phase", "idle")

    # ══════════════════════════════════════════════════════════════════════════
    # GENERAL HINTS FLOW
    # ══════════════════════════════════════════════════════════════════════════
    if hint_mode == "general":

        solution_text = problem.tutorial.solution or ""
        if not solution_text and problem.tutorial.hints:
            solution_text = " ".join(problem.tutorial.hints)

        if not solution_text:
            st.warning(
                "No official solution text available for this problem. "
                "Concept extraction requires the editorial."
            )
            st.stop()

        # ── Phase: extracting concepts ────────────────────────────────────
        if phase == "extracting":
            with st.spinner("Extracting key concepts from the problem + editorial…"):
                try:
                    concepts = extract_concepts(
                        statement=problem.statement or "",
                        solution=solution_text,
                    )
                    if not concepts:
                        st.error("LLM returned no concepts. Check that Ollama is running.")
                        st.session_state["phase"] = "idle"
                        st.rerun()
                    else:
                        st.session_state["concepts"] = concepts
                        st.session_state["topo_order"] = topological_sort(concepts)
                        st.session_state["phase"] = "questioning"
                        st.session_state["question_idx"] = 0
                        st.session_state["understood_ids"] = []
                        st.rerun()
                except Exception as exc:
                    st.error(f"Concept extraction failed: {exc}")
                    st.session_state["phase"] = "idle"

        # ── Phase: questioning ────────────────────────────────────────────
        elif phase == "questioning":
            concepts: list[Concept] = _ss("concepts", [])
            topo_order: list[str] = _ss("topo_order", [])
            question_idx: int = _ss("question_idx", 0)
            understood_ids: list[str] = _ss("understood_ids", [])

            # Concept map expander
            with st.expander("📊 Concept map", expanded=False):
                for c in concepts:
                    tick = "✓" if c.id in understood_ids else "·"
                    prereq_str = (
                        f"  _(requires: {', '.join(c.prerequisites)})_"
                        if c.prerequisites
                        else ""
                    )
                    st.markdown(f"**{tick} {c.name}**{prereq_str}")

            # Progress bar
            total = max(len(topo_order), 1)
            st.progress(min(question_idx / total, 1.0))
            st.caption(f"Question {question_idx + 1} of {total}")

            if question_idx >= len(topo_order):
                # Student answered "yes" to all concepts — session complete
                st.success("🎉 You understand all key concepts for this problem!")
                st.markdown("You answered **Yes** to every concept in the DAG.")

                last_concept = get_concept_by_id(concepts, topo_order[-1]) if topo_order else None
                if last_concept:
                    st.markdown("---")
                    st.caption(
                        "If you still want a challenge, you can request hints "
                        "for the hardest concept:"
                    )
                    if st.button(
                        f"Generate hints for **{last_concept.name}** anyway",
                        key="optional_final_hints",
                    ):
                        st.session_state["missing_concept"] = last_concept
                        st.session_state["phase"] = "generating_hints"
                        # Temporarily step back so Continue won't loop
                        st.session_state["question_idx"] = len(topo_order) - 1
                        st.rerun()

            else:
                current_concept = get_concept_by_id(concepts, topo_order[question_idx])
                if current_concept:
                    st.markdown("### Do you understand this concept?")
                    st.info(f"**{current_concept.name}**")
                    yes_col, no_col = st.columns(2)
                    with yes_col:
                        if st.button(
                            "✓  Yes, I understand",
                            use_container_width=True,
                            key=f"yes_{question_idx}",
                        ):
                            understood_ids.append(current_concept.id)
                            st.session_state["understood_ids"] = understood_ids
                            st.session_state["question_idx"] = question_idx + 1
                            st.rerun()
                    with no_col:
                        if st.button(
                            "✗  No, I need help with this",
                            use_container_width=True,
                            key=f"no_{question_idx}",
                        ):
                            st.session_state["missing_concept"] = current_concept
                            st.session_state["phase"] = "generating_hints"
                            st.rerun()

        # ── Phase: generating hints ───────────────────────────────────────
        elif phase == "generating_hints":
            missing_concept: Concept | None = _ss("missing_concept")
            if missing_concept is None:
                st.error("No concept identified. Please restart.")
                st.session_state["phase"] = "questioning"
            else:
                with st.spinner(
                    f"Generating hints for **{missing_concept.name}**…"
                ):
                    try:
                        hints, prompt_json = _call_hint_llm_general(
                            problem, missing_concept
                        )
                        st.session_state["generated_hints"] = hints
                        st.session_state["hint_prompt_json"] = prompt_json
                        st.session_state["phase"] = "rating"
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Hint generation failed: {exc}")
                        st.session_state["phase"] = "questioning"

        # ── Phase: rating ─────────────────────────────────────────────────
        elif phase == "rating":
            _render_rating_section(selected_problem_id, selected_submission, "general")

    # ══════════════════════════════════════════════════════════════════════════
    # SPECIFIC HINTS FLOW
    # ══════════════════════════════════════════════════════════════════════════
    elif hint_mode == "specific":

        solution_text = problem.tutorial.solution or ""

        # Code area — pre-filled from selected submission
        default_code = selected_submission.code if selected_submission else ""
        student_code = st.text_area(
            "Student code", value=default_code, height=300, key="student_code_area"
        )

        # ── Phase: idle ───────────────────────────────────────────────────
        if phase == "idle":
            if not student_code.strip():
                st.info("Select a submission on the left (or paste code above), then click Analyze.")
            if st.button("🔬  Analyze Code & Generate Hints", use_container_width=True):
                if not student_code.strip():
                    st.warning("Please provide some student code before analyzing.")
                else:
                    st.session_state["student_code_snapshot"] = student_code
                    st.session_state["selected_submission_key"] = (
                        selected_submission.submission_id if selected_submission else None
                    )
                    st.session_state["phase"] = "extracting"
                    st.rerun()

        # ── Phase: extracting (concepts + code analysis) ──────────────────
        elif phase == "extracting":
            code_snap = _ss("student_code_snapshot", student_code)
            verdict = selected_submission.verdict if selected_submission else "UNKNOWN"

            with st.spinner("Step 1/2 — Extracting concepts from the editorial…"):
                try:
                    concepts = extract_concepts(
                        statement=problem.statement or "",
                        solution=solution_text or "No editorial available.",
                    )
                except Exception as exc:
                    st.error(f"Concept extraction failed: {exc}")
                    st.session_state["phase"] = "idle"
                    st.stop()

            if not concepts:
                st.error("Could not extract concepts. Check Ollama is running.")
                st.session_state["phase"] = "idle"
                st.stop()

            with st.spinner("Step 2/2 — Analysing student code to identify missing concept…"):
                try:
                    analysis_prompt = build_code_analysis_prompt(
                        statement=problem.statement or "",
                        solution_text=solution_text,
                        solution_code=problem.tutorial.code,
                        student_code=code_snap,
                        test_data=test_data,
                        verdict=verdict,
                        concepts=concepts,
                    )
                    raw = ollama_chat(
                        user_prompt=analysis_prompt,
                        system_prompt="Return only valid JSON.",
                        temperature=0.3,
                    )
                    analysis_data = parse_json_response(raw)
                    missing_id = str(analysis_data.get("missing_concept_id", "")).strip()
                    reason = str(analysis_data.get("reason", "")).strip()
                except Exception as exc:
                    st.error(f"Code analysis failed: {exc}")
                    st.session_state["phase"] = "idle"
                    st.stop()

            missing_concept = get_concept_by_id(concepts, missing_id)
            if missing_concept is None and concepts:
                missing_concept = concepts[0]
                reason = reason or "Analysis could not pinpoint the exact concept."

            st.session_state["concepts"] = concepts
            st.session_state["topo_order"] = topological_sort(concepts)
            st.session_state["missing_concept"] = missing_concept
            st.session_state["analysis_reason"] = reason
            st.session_state["phase"] = "generating_hints"
            st.rerun()

        # ── Phase: generating hints ───────────────────────────────────────
        elif phase == "generating_hints":
            missing_concept = _ss("missing_concept")
            reason = _ss("analysis_reason", "")

            if missing_concept:
                st.success(f"**Identified missing concept:** {missing_concept.name}")
                if reason:
                    st.caption(f"Analysis: {reason}")

            with st.spinner(
                f"Generating targeted hints for **{missing_concept.name if missing_concept else '…'}**…"
            ):
                code_snap = _ss("student_code_snapshot", student_code)
                try:
                    hints, prompt_json = _call_hint_llm_specific(
                        problem=problem,
                        submission=selected_submission,
                        student_code=code_snap,
                        concept=missing_concept,
                        reason=reason,
                    )
                    st.session_state["generated_hints"] = hints
                    st.session_state["hint_prompt_json"] = prompt_json
                    st.session_state["phase"] = "rating"
                    st.rerun()
                except Exception as exc:
                    st.error(f"Hint generation failed: {exc}")
                    st.session_state["phase"] = "idle"

        # ── Phase: rating ─────────────────────────────────────────────────
        elif phase == "rating":
            missing_concept = _ss("missing_concept")
            reason = _ss("analysis_reason", "")
            if missing_concept:
                st.success(f"**Identified missing concept:** {missing_concept.name}")
                if reason:
                    st.caption(f"Analysis: {reason}")
            _render_rating_section(selected_problem_id, selected_submission, "specific")

    # ── Idle / no mode selected ───────────────────────────────────────────────
    else:
        st.info("Choose a hint mode above to begin.")
        st.markdown(
            """
**General Hints** — The system extracts key concepts from the problem's editorial,
then asks you binary questions (`Yes / No`) to find which concept you're missing,
and generates 2 targeted hints for that concept.

**Specific Hints** — Select (or paste) a wrong submission.
The system analyses your code against the official solution to automatically
identify the missing concept, then generates 2 hints pinpointed to your specific mistake.

            """
        )
