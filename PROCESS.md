# PROCESS (Template)

Use this template to document how this project was built primarily through prompt-driven (AI-assisted) development.

## 1) Summary

- **Project name:** Flashcard Tutor (Gradio + LLM)
- **Goal:** Provide study notes (paste text or upload PDF) → generate flashcards (LLM or offline) → quiz with scoring
- **Primary approach:** Natural-language instructions to an AI coding assistant, iterating until the app worked end-to-end.

## 2) AI assistant usage

- **Tool/assistant used:** (Fill in: e.g., Windsurf Cascade)
- **How the assistant was used:**
  - Convert high-level requirements into code structure
  - Implement features (Gradio UI, generation pipeline, quiz state)
  - Debug dependency issues and runtime errors
  - Add validation, structured outputs, and retry/repair behavior

- **Example prompts used (copy/paste a few):**
  - "Build a fully functional Python application using Gradio..."
  - "Implement automatic flashcard generation using an LLM... enforce JSON-only output"
  - "Add a PDF upload option to extract study text"
  - "Improve flashcard quality and prevent dumping the entire text into one card"
  - "Add robust error handling across the entire app"

## 3) Prompt-driven development notes

Describe how requirements were incrementally introduced and implemented.

- **Iteration 1 (MVP):**
  - Generated flashcards from pasted text
  - Basic quiz mode

- **Iteration 2 (Reliability):**
  - Structured JSON output from LLM
  - Validation + repair step when malformed

- **Iteration 3 (UX):**
  - Simplified two-tab UI (Generate/Quiz)
  - Student-friendly layout
  - Added PDF upload → text extraction
  - Added a UI toggle to enable/disable LLM generation

- **Iteration 4 (Submission readiness):**
  - README + PROCESS docs
  - Robust defensive error handling

## 4) Challenges encountered and fixes

Record the main issues and what you did about them.

- **Python launcher on Windows (`python` not found):**
  - Used `py` instead of `python`

- **Python 3.13 dependency issues:**
  - `pydub` import issue due to removed `audioop`
  - Fix: added `audioop-lts`

- **Gradio / huggingface_hub incompatibility:**
  - `ImportError: cannot import name 'HfFolder'`
  - Fix: pinned `huggingface_hub==0.23.5`

- **LLM output not valid JSON:**
  - Fix: extract JSON array + validate schema + repair pass prompting

- **LLM output quality issues (too long / generic cards):**
  - Fix: enforce max question/answer lengths, reject generic questions, and refine prompts

- **PDF upload limitations:**
  - Fix: added PDF parsing via `pypdf` for text-based PDFs; documented that scanned PDFs need OCR

- **OpenAI quota/billing errors (HTTP 429 insufficient_quota):**
  - Fix: user-facing error messaging; added a UI toggle to fall back to offline generation when desired

- **Gradio schema/local-host edge cases in some environments:**
  - Fix: runtime patches to tolerate schema boolean fields and proxy-related localhost checks

- **UI/quiz state bugs:**
  - Fix: store quiz state in a single dict and update it only through button handlers

## 5) Defensive programming in AI-driven apps (why it mattered)

AI-driven apps have additional failure modes:
- Network timeouts / rate limits
- Missing API keys
- Non-deterministic or malformed model output

Explain how you handled these defensively:
- Validate study text before sending to the model
- Force JSON-only structured output
- Validate schema and retry/repair output
- Catch exceptions and show user-friendly error messages instead of crashing
 - Add guardrails against overly long or generic cards

## 6) AI-generated vs manual work estimate

Provide an honest estimate:

- **AI-generated code:** ____ %
- **Manual edits (human):** ____ %

Explain what was manual vs AI-assisted:
- Manual: deciding requirements, verifying runtime behavior, selecting what to keep
- AI-assisted: implementing modules, Gradio wiring, validation logic, quality guardrails, and error handling

## 7) How to reproduce

- Install dependencies:
  - `py -m pip install -r NLP\requirements.txt`
- Run:
  - `py NLP\app.py`

## 8) Appendix (optional)

- Screenshots
- Example study text used for testing
- Example generated deck output
