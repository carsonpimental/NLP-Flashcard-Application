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

## AI Prompt Interactions

<img width="720" height="1248" alt="Screenshot 2026-01-21 235628" src="https://github.com/user-attachments/assets/f4858bf3-1520-4429-87ae-2af6337b989f" />
<img width="700" height="1460" alt="Screenshot 2026-01-21 235701" src="https://github.com/user-attachments/assets/3366b1a8-ce8b-4e0d-a1de-135890bcdaf3" />
<img width="729" height="1427" alt="Screenshot 2026-01-21 235715" src="https://github.com/user-attachments/assets/a315d564-8ffd-4700-af1a-30906b282663" />
<img width="725" height="1462" alt="Screenshot 2026-01-21 235730" src="https://github.com/user-attachments/assets/2308a397-da5e-44b2-b8b4-a08501bd14b0" />
<img width="733" height="1521" alt="Screenshot 2026-01-21 235749" src="https://github.com/user-attachments/assets/5e9aa9a2-046f-4e9e-8a56-68b3ea4d4a2f" />
<img width="740" height="1414" alt="Screenshot 2026-01-21 235811" src="https://github.com/user-attachments/assets/4674b0cc-a003-4164-9d51-0e106ce3a83b" />
<img width="725" height="1455" alt="Screenshot 2026-01-21 235822" src="https://github.com/user-attachments/assets/92350b2a-14a3-473a-832f-c62287a85dec" />
<img width="738" height="1372" alt="Screenshot 2026-01-21 235955" src="https://github.com/user-attachments/assets/6ff142c1-6133-495a-9167-6a0c00e754fb" />






