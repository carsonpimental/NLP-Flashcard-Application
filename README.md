# Flashcard Tutor (Gradio + LLM)

A small Python application that turns pasted study material into flashcards, then quizzes you on them with scoring.

This project was built primarily from natural-language instructions (see `PROCESS.md`).

## What the app does

- Provide study material as **text** (paste) or upload a **PDF**
- Generate a flashcard **deck**
  - Uses ChatGPT/OpenAI if enabled and configured
  - Can fall back to an offline deterministic generator if you disable LLM generation
- Quiz yourself in **Quiz** mode
  - Reveal answer
  - Mark correct / incorrect
  - Track accuracy

## Project structure

- `NLP/app.py`
  - Gradio UI (Blocks)
  - State management (generated flashcards + quiz state)
- `NLP/flashcards.py`
  - Flashcard and Deck data structures
  - LLM prompt + JSON validation + repair logic
  - Fallback generator
- `NLP/llm_client.py`
  - OpenAI SDK wrapper
  - Timeout handling + user-friendly exceptions
- `NLP/requirements.txt`
  - Python dependencies

## Setup & run

### Prerequisites

- Python installed
- On Windows, you may need to use the `py` launcher (recommended).

### 1) (Recommended) Create a virtual environment

From the repo root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
py -m pip install -r NLP\requirements.txt
```

### 3) Run the app

```powershell
py NLP\app.py
```

Gradio will print a local URL such as:

- `http://127.0.0.1:7860`

Open it in your browser.

## Enable LLM flashcard generation (optional)

If you set an OpenAI API key and leave **Use ChatGPT (LLM) for generation** enabled in the UI, the generator will use the LLM.

Set the environment variable:

- `OPENAI_API_KEY`

Optional:

- `OPENAI_MODEL` (defaults to `gpt-4o-mini`)
- `OPENAI_TIMEOUT_SECONDS` (defaults to `30`)

Example (PowerShell):

```powershell
$env:OPENAI_API_KEY = "your_key_here"
py NLP\app.py
```

## How to use the UI

### Tab 1: Generate

1. Provide study material using either:
   - Paste text into the large textbox, or
   - Upload a PDF and click **Use PDF as Study Material** (the extracted text will fill the textbox)
2. Choose:
   - number of flashcards
   - whether to use ChatGPT (LLM) for generation
   - style (Q/A, Definition, Cloze)
   - difficulty (easy/medium/hard)
3. Click **Generate Flashcards**.
4. Review the table.

Note: If a PDF is scanned images (no selectable text), this app will not extract text by itself; you will need OCR first.

### Tab 2: Quiz

1. Click **Start / Restart Quiz**.
2. For each card:
   - Click **Reveal Answer**
   - Mark **Correct** or **Incorrect**
   - Click **Next Question**
3. Watch the score summary update (correct/incorrect/answered/accuracy).

## Notes / troubleshooting

- If you receive an OpenAI error like `429 insufficient_quota`, your OpenAI account may need billing/credits.
- If you don't want to use the LLM, uncheck **Use ChatGPT (LLM) for generation** and the app will use the offline fallback generator.
- If you see an error on launch, re-run from a clean terminal and check the printed traceback.
