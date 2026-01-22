"""app.py

A fully functional Gradio app that:
1) Accepts pasted study material text
2) Generates flashcards (LLM if configured, otherwise deterministic fallback)
3) Quizzes the user with scoring

How to run:
- Create and activate a virtual environment
- pip install -r requirements.txt
- python app.py

Optional (for best flashcards):
- Set OPENAI_API_KEY in your environment
- Optionally set OPENAI_MODEL (defaults to gpt-4o-mini)

This file focuses on UI + state management.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

import gradio as gr


def _patch_gradio_client_schema_bug() -> None:
    """Work around a Gradio client schema conversion bug.

    Defensive programming note:
    - In some environments, Gradio builds an OpenAPI-ish schema at runtime.
    - Certain JSON Schema fields (like `additionalProperties`) are allowed to be
      booleans (`true`/`false`).
    - `gradio_client` versions pinned by Gradio may assume these are dicts and crash.

    This patch keeps the app running (and the UI usable) even if API schema
    generation hits that edge case.
    """

    try:
        # Many corporate/proxy setups break localhost requests unless NO_PROXY is set.
        # Gradio internally checks whether it can reach the locally-started server.
        # If that check goes through a proxy, Gradio may incorrectly decide localhost
        # is "not accessible" and refuse to start without `share=True`.
        os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
        os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

        import gradio_client.utils as client_utils

        original_get_type = client_utils.get_type
        original_json_schema_to_python_type = client_utils.json_schema_to_python_type
        original__json_schema_to_python_type = getattr(client_utils, "_json_schema_to_python_type", None)

        def safe_get_type(schema):  # type: ignore[no-untyped-def]
            if not isinstance(schema, dict):
                return "any"
            return original_get_type(schema)

        def safe_json_schema_to_python_type(schema):  # type: ignore[no-untyped-def]
            # JSON Schema allows the schema itself to be a boolean.
            # `true` means "anything is valid" and `false` means "nothing is valid".
            # Some Gradio schema generation paths pass these through and older
            # gradio_client versions crash when expecting a dict.
            if isinstance(schema, bool):
                return "any"
            return original_json_schema_to_python_type(schema)

        def safe__json_schema_to_python_type(schema, defs=None):  # type: ignore[no-untyped-def]
            # Lower-level helper used by json_schema_to_python_type. We patch this too
            # because the error we saw was an APIInfoParseError("Cannot parse schema True").
            if isinstance(schema, bool):
                return "any"
            if original__json_schema_to_python_type is None:
                return "any"
            return original__json_schema_to_python_type(schema, defs)

        client_utils.get_type = safe_get_type  # type: ignore[assignment]
        client_utils.json_schema_to_python_type = safe_json_schema_to_python_type  # type: ignore[assignment]
        if original__json_schema_to_python_type is not None:
            client_utils._json_schema_to_python_type = safe__json_schema_to_python_type  # type: ignore[attr-defined]
    except Exception:
        # If patching fails for any reason, we don't block app startup.
        return


def _patch_gradio_runtime() -> None:
    """Patch Gradio internals to keep the app usable in locked-down environments.

    Why this exists:
    - Some proxy configurations make Gradio think localhost is not reachable, and
      Gradio then refuses to start unless `share=True`.
    - Some Gradio versions also attempt to generate an API schema at runtime.
      On Python 3.13 + pinned `gradio_client`, a valid JSON Schema boolean
      (`true`/`false`) can trigger an exception.

    We patch one thing:
    - `gradio.networking.url_ok` -> always True (skip the localhost probe)

    This keeps the UI running locally so you can use the app normally.
    """

    try:
        import gradio.networking as gr_networking

        gr_networking.url_ok = lambda _url: True  # type: ignore[assignment]
    except Exception:
        return


_patch_gradio_client_schema_bug()
_patch_gradio_runtime()

from flashcards import Flashcard, cards_to_table, generate_flashcards
from llm_client import has_openai_key


def _cards_to_json(cards: List[Flashcard]) -> str:
    """Serialize cards to pretty JSON for display / debugging."""

    return json.dumps([asdict(c) for c in cards], indent=2, ensure_ascii=False)


def _preprocess_study_text(raw_text: str) -> Tuple[Optional[str], Optional[str]]:
    """Validate and clean study material input.

    Why preprocessing matters before LLM usage:
    - Users often paste notes that include inconsistent whitespace, copied headers/footers,
      or accidental extra blank lines.
    - Normalizing whitespace makes the prompt more compact and predictable, which reduces
      token waste and improves generation quality.
    - A minimum length check prevents sending near-empty prompts to the LLM (or our
      fallback generator), which would produce low-quality flashcards.

    Returns:
    - (clean_text, None) when valid
    - (None, error_message) when invalid
    """

    if raw_text is None:
        return None, "Please paste your study notes in the textbox."

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    # Whitespace normalization: collapse trailing spaces and overly-long blank sections.
    text = re.sub(r"[\t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    if not text:
        return None, "Please paste your study notes — the input is currently empty."

    # Simple minimum length validation.
    # We use characters (not tokens) since it’s fast and does not depend on any tokenizer.
    min_chars = 120
    if len(text) < min_chars:
        return (
            None,
            (
                "Your study material looks too short to generate useful flashcards. "
                f"Please paste at least ~{min_chars} characters (a few paragraphs) and try again."
            ),
        )

    return text, None


def _extract_text_from_pdf(pdf_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract text from a PDF file path.

    This is used to let students upload a PDF instead of copy/pasting text.
    We keep extraction separate from flashcard generation so failures are
    handled early with clear messages.
    """

    if not pdf_path:
        return None, "No PDF file was provided."

    try:
        from pypdf import PdfReader
    except Exception:
        return None, "PDF support is not installed. Please install dependencies from requirements.txt."

    try:
        reader = PdfReader(pdf_path)
        if getattr(reader, "is_encrypted", False):
            return None, "This PDF appears to be encrypted/password-protected and cannot be read."

        chunks: List[str] = []
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            if txt.strip():
                chunks.append(txt)

        text = "\n\n".join(chunks)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        if not text:
            return (
                None,
                "No extractable text was found in that PDF. "
                "If it's a scanned document, you may need OCR before using this app.",
            )

        return text, None
    except Exception as e:
        return None, f"Failed to read PDF: {e}"


def ui_load_pdf(pdf_file) -> Tuple[str, str]:
    """Load a PDF and populate the Study Material textbox.

    Returns:
    - extracted_text (to put into the textbox)
    - status markdown
    """

    try:
        if pdf_file is None:
            return "", "**Error:** Please upload a PDF file."

        # Depending on Gradio version/config, this can be a path string or an object.
        pdf_path = getattr(pdf_file, "name", None) or str(pdf_file)
        text, err = _extract_text_from_pdf(pdf_path)
        if err:
            return "", f"**Error:** {err}"

        return text or "", "**Loaded PDF text.** You can edit it before generating flashcards."
    except Exception as e:
        return "", f"**Error:** Failed to process PDF upload: {e}"


def ui_generate(
    study_text: str,
    n_cards: int,
    style: str,
    difficulty: str,
    use_llm: bool,
) -> Tuple[List[List[str]], str, str, List[Dict[str, str]]]:
    """Generate flashcards from the provided text.

    Returns values mapped to UI components:
    - table rows
    - status markdown
    - raw output text
    - cards_state (list[dict])
    """

    # Defensive programming note:
    # AI-driven apps have more failure modes than typical CRUD apps:
    # - network calls can time out
    # - models can return malformed output
    # - users can paste unexpected input
    # We *always* catch exceptions and turn them into a clear message so the UI never crashes.

    cleaned_text, err = _preprocess_study_text(study_text)
    if err:
        return [], f"**Error:** {err}", "", []

    try:
        cards, mode, raw = generate_flashcards(
            cleaned_text,
            n_cards,
            style=style,
            difficulty=difficulty,
            use_llm=bool(use_llm),
        )
    except Exception as e:
        # Typical causes:
        # - Missing API key (if the user expects LLM mode)
        # - LLM timeout / network failure
        # - Malformed model output that couldn't be repaired
        msg = str(e).strip() or "Unknown error"
        return [], f"**Error:** {msg}", msg, []

    if mode == "fallback":
        status = (
            f"**Generated {len(cards)} flashcards.** Mode: `{mode}`\n\n"
            "**Note:** Using offline fallback generation (LLM disabled or unavailable).\n\n"
            "Go to the **Quiz** tab to start practicing."
        )
    else:
        status = (
            f"**Generated {len(cards)} flashcards.** Mode: `{mode}`\n\n"
            "Go to the **Quiz** tab to start practicing."
        )

    cards_state = [asdict(c) for c in cards]

    return cards_to_table(cards), status, raw, cards_state


def _quiz_init_state(cards_state: List[Dict[str, str]]) -> Dict:
    """Create a fresh quiz session state."""

    return {
        "cards": cards_state or [],
        "idx": 0,
        # Quiz state is stored in a single dict so Gradio can persist it across button clicks.
        # Fields:
        # - cards: the generated flashcards (list of dicts)
        # - idx: which card we're currently showing
        # - revealed: whether the answer is currently revealed
        # - marked: whether the current question has been marked correct/incorrect
        # - correct/incorrect/answered: running totals for scoring
        "revealed": False,
        "marked": False,
        "correct": 0,
        "incorrect": 0,
        "answered": 0,
        "history": [],  # list of dicts per question
        "finished": False,
    }


def _quiz_score_text(state: Dict) -> str:
    """Compute a user-friendly score summary."""

    answered = int(state.get("answered", 0))
    correct = int(state.get("correct", 0))
    incorrect = int(state.get("incorrect", 0))
    acc = (correct / answered * 100.0) if answered else 0.0

    return (
        f"Correct: **{correct}**\n\n"
        f"Incorrect: **{incorrect}**\n\n"
        f"Total answered: **{answered}**\n\n"
        f"Accuracy: **{acc:.1f}%**"
    )


def _quiz_progress_text(state: Dict) -> str:
    cards = state.get("cards", []) or []
    idx = int(state.get("idx", 0))
    if not cards:
        return ""
    if state.get("finished"):
        return f"Finished! {len(cards)} / {len(cards)}"
    return f"Question {idx+1} / {len(cards)}"


def _quiz_current_question(state: Dict) -> str:
    cards = state.get("cards", []) or []
    idx = int(state.get("idx", 0))
    if not cards or idx < 0 or idx >= len(cards):
        return ""
    return cards[idx].get("question", "")


def _quiz_current_answer(state: Dict) -> str:
    cards = state.get("cards", []) or []
    idx = int(state.get("idx", 0))
    if not cards or idx < 0 or idx >= len(cards):
        return ""
    return cards[idx].get("answer", "")


def ui_start_quiz(cards_state: List[Dict[str, str]]) -> Tuple[Dict, str, str, str, str]:
    """Start a new quiz based on the current flashcards.

    We prevent starting if the user hasn't generated flashcards yet.
    """

    if not cards_state:
        empty_state = _quiz_init_state([])
        return (
            empty_state,
            "**Error:** No flashcards yet. Generate flashcards first.",
            "",
            "",
            "",
        )

    state = _quiz_init_state(cards_state)
    return (
        state,
        _quiz_progress_text(state),
        _quiz_current_question(state),
        _quiz_score_text(state),
        "",
    )


def ui_reveal_answer(quiz_state: Dict) -> Tuple[Dict, str, str, str, str]:
    """Reveal the current answer.

    This does not change scoring. It only flips `revealed=True` so the UI can show
    the answer for the current card.
    """

    try:
        if not quiz_state or not quiz_state.get("cards"):
            return quiz_state, "", "", "", "**Error:** Start the quiz first."

        if quiz_state.get("finished"):
            return quiz_state, _quiz_progress_text(quiz_state), "", _quiz_score_text(quiz_state), "Quiz is finished."

        quiz_state["revealed"] = True
        answer = _quiz_current_answer(quiz_state)
        return (
            quiz_state,
            _quiz_progress_text(quiz_state),
            _quiz_current_question(quiz_state),
            _quiz_score_text(quiz_state),
            f"**Answer:** {answer}",
        )
    except Exception as e:
        return quiz_state, "", "", "", f"**Error:** {e}"


def ui_mark_answer(quiz_state: Dict, is_correct: bool) -> Tuple[Dict, str, str, str, str]:
    """Mark the current question as correct or incorrect.

    We record the result in `history` and increment running totals. We also set
    `marked=True` so the UI can encourage moving on to the next question.
    """

    try:
        if not quiz_state or not quiz_state.get("cards"):
            return quiz_state, "", "", "", "**Error:** Start the quiz first."

        if quiz_state.get("finished"):
            return (
                quiz_state,
                _quiz_progress_text(quiz_state),
                "",
                _quiz_score_text(quiz_state),
                "Quiz is finished.",
            )

        if quiz_state.get("marked"):
            return (
                quiz_state,
                _quiz_progress_text(quiz_state),
                _quiz_current_question(quiz_state),
                _quiz_score_text(quiz_state),
                "You already marked this question. Click **Next Question**.",
            )

        cards = quiz_state.get("cards", [])
        idx = int(quiz_state.get("idx", 0))
        if idx < 0 or idx >= len(cards):
            quiz_state["finished"] = True
            return (
                quiz_state,
                _quiz_progress_text(quiz_state),
                "",
                _quiz_score_text(quiz_state),
                "Quiz is finished.",
            )

        quiz_state["answered"] = int(quiz_state.get("answered", 0)) + 1
        if is_correct:
            quiz_state["correct"] = int(quiz_state.get("correct", 0)) + 1
        else:
            quiz_state["incorrect"] = int(quiz_state.get("incorrect", 0)) + 1

        quiz_state["marked"] = True
        quiz_state["history"].append(
            {
                "question": cards[idx].get("question", ""),
                "answer": cards[idx].get("answer", ""),
                "type": cards[idx].get("type", ""),
                "difficulty": cards[idx].get("difficulty", ""),
                "result": "correct" if is_correct else "incorrect",
            }
        )

        verdict = "Correct" if is_correct else "Incorrect"
        return (
            quiz_state,
            _quiz_progress_text(quiz_state),
            _quiz_current_question(quiz_state),
            _quiz_score_text(quiz_state),
            f"Marked **{verdict}**. Click **Next Question**.",
        )
    except Exception as e:
        return quiz_state, "", "", "", f"**Error:** {e}"


def ui_next_question(quiz_state: Dict) -> Tuple[Dict, str, str, str, str]:
    """Advance to the next question and reset per-question flags."""

    try:
        if not quiz_state or not quiz_state.get("cards"):
            return quiz_state, "", "", "", "**Error:** Start the quiz first."

        if quiz_state.get("finished"):
            return (
                quiz_state,
                _quiz_progress_text(quiz_state),
                "",
                _quiz_score_text(quiz_state),
                "Quiz is finished.",
            )

        cards = quiz_state.get("cards", [])
        idx = int(quiz_state.get("idx", 0)) + 1
        quiz_state["idx"] = idx
        quiz_state["revealed"] = False
        quiz_state["marked"] = False

        if idx >= len(cards):
            quiz_state["finished"] = True
            return (
                quiz_state,
                _quiz_progress_text(quiz_state),
                "",
                _quiz_score_text(quiz_state),
                "Quiz is finished.",
            )

        return (
            quiz_state,
            _quiz_progress_text(quiz_state),
            _quiz_current_question(quiz_state),
            _quiz_score_text(quiz_state),
            "",
        )
    except Exception as e:
        return quiz_state, "", "", "", f"**Error:** {e}"


with gr.Blocks(title="Flashcard Tutor") as demo:
    gr.Markdown(
        "# Flashcard Tutor\n"
        "Generate flashcards from your notes, then quiz yourself."  # noqa: E501
    )

    cards_state = gr.State([])  # list[dict]
    quiz_state = gr.State({})

    with gr.Tabs():
        with gr.TabItem("Generate"):
            # UI decision: tabs keep the app mentally simple for students (Create first, Practice second).
            # UI decision: left-to-right layout mirrors a student's workflow (input → output).
            with gr.Row():
                with gr.Column(scale=5):
                    gr.Markdown("## Study Material")

                    # Optional input path: upload a PDF and extract its text into the textbox.
                    # This is helpful when students have readings/handouts as PDFs.
                    pdf_file = gr.File(label="Upload PDF (optional)", file_types=[".pdf"], type="filepath")
                    load_pdf_btn = gr.Button("Use PDF as Study Material")

                    study_text = gr.Textbox(
                        label="Paste your notes",
                        lines=16,
                        placeholder="Paste your notes, textbook excerpt, or lecture transcript here...",
                    )

                    # UI decision: controls are grouped together so users can set preferences in one place.
                    with gr.Row():
                        n_cards = gr.Slider(
                            label="# of flashcards",
                            minimum=3,
                            maximum=30,
                            value=10,
                            step=1,
                        )
                        use_llm = gr.Checkbox(
                            label="Use ChatGPT (LLM) for generation",
                            value=True,
                        )
                        style = gr.Dropdown(
                            label="Style",
                            choices=["Q/A", "Definition", "Cloze"],
                            value="Q/A",
                        )
                        difficulty = gr.Dropdown(
                            label="Difficulty",
                            choices=["easy", "medium", "hard"],
                            value="medium",
                        )

                    generate_btn = gr.Button("Generate Flashcards", variant="primary")

                with gr.Column(scale=6):
                    # UI decision: status/error is placed above results so feedback is impossible to miss.
                    status_md = gr.Markdown("")

                    table = gr.Dataframe(
                        headers=["Type", "Difficulty", "Question", "Answer"],
                        datatype=["str", "str", "str", "str"],
                        label="Generated Flashcards",
                        wrap=True,
                        interactive=False,
                    )

                    with gr.Accordion("Advanced (debug)", open=False):
                        raw_out = gr.Textbox(label="LLM raw output", lines=8)
                        cards_json = gr.Code(label="cards.json", language="json")

            def _update_json(state_cards: List[Dict[str, str]]):
                return json.dumps(state_cards, indent=2, ensure_ascii=False)

            generate_btn.click(
                fn=ui_generate,
                inputs=[study_text, n_cards, style, difficulty, use_llm],
                outputs=[table, status_md, raw_out, cards_state],
            ).then(
                fn=_update_json,
                inputs=[cards_state],
                outputs=[cards_json],
            )

            load_pdf_btn.click(
                fn=ui_load_pdf,
                inputs=[pdf_file],
                outputs=[study_text, status_md],
            )

        with gr.TabItem("Quiz"):
            gr.Markdown(
                "## Quiz Mode\n"
                "One question at a time. Reveal the answer, mark it correct/incorrect, then move on."  # noqa: E501
            )

            start_btn = gr.Button("Start / Restart Quiz", variant="primary")

            with gr.Row():
                progress_txt = gr.Markdown("")
                score_txt = gr.Markdown("")

            gr.Markdown("### Question")
            question_txt = gr.Markdown("")

            gr.Markdown("### Answer / Status")
            feedback_md = gr.Markdown("")

            with gr.Row():
                reveal_btn = gr.Button("Reveal Answer")
                correct_btn = gr.Button("Correct", variant="primary")
                incorrect_btn = gr.Button("Incorrect")
                next_btn = gr.Button("Next Question")

            start_btn.click(
                fn=ui_start_quiz,
                inputs=[cards_state],
                outputs=[quiz_state, progress_txt, question_txt, score_txt, feedback_md],
            )

            reveal_btn.click(
                fn=ui_reveal_answer,
                inputs=[quiz_state],
                outputs=[quiz_state, progress_txt, question_txt, score_txt, feedback_md],
            )

            correct_btn.click(
                fn=lambda s: ui_mark_answer(s, True),
                inputs=[quiz_state],
                outputs=[quiz_state, progress_txt, question_txt, score_txt, feedback_md],
            )

            incorrect_btn.click(
                fn=lambda s: ui_mark_answer(s, False),
                inputs=[quiz_state],
                outputs=[quiz_state, progress_txt, question_txt, score_txt, feedback_md],
            )

            next_btn.click(
                fn=ui_next_question,
                inputs=[quiz_state],
                outputs=[quiz_state, progress_txt, question_txt, score_txt, feedback_md],
            )


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", share=False, show_api=False)
