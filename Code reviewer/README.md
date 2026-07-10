# Intelligent Code Reviewer & Explainer

DecodeLabs — Generative AI, Project 4 (Optional Mastery Phase)

A CLI developer utility that ingests a raw source file, sends it to a
generative model locked behind a strict reviewer persona, and prints a
structured, syntax-highlighted **Bug Report + Refactored Code** straight to
your terminal.

## How it works (the pipeline)

```
Raw File  ->  Payload Capture  ->  Context Orchestration  ->  Structured
(.py/.js/    (read as string,      (system instruction        Output
 .java)       preserve exact        locks the model into a     Validation
              whitespace)           fixed persona + format)    -> Rendered
                                                                    Markdown
```

1. **Ingest** — `read_source_file()` opens the target file and reads it as
   a raw string, preserving all whitespace/indentation exactly. Handles
   `FileNotFoundError`, `PermissionError`, and `UnicodeDecodeError`
   gracefully instead of crashing.
2. **Orchestrate** — the code is wrapped in a prompt and sent to the model
   together with a `SYSTEM_INSTRUCTION` that strips away all conversational
   behavior ("Sure, here's your code!") and forces the model to act as a
   cold, deterministic QA engineer.
3. **Validate** — the model's raw text response is checked for the two
   required headers, `## BUG_REPORT` and `## REFACTORED_CODE`, in the
   correct order. If either is missing, the response is rejected and never
   shown — a malformed report never reaches you.
4. **Render** — once verified, the Markdown is handed to `rich.markdown.Markdown`,
   which prints it to the terminal with color-mapped syntax highlighting for
   the fenced code block.

## Setup

```bash
pip install -r requirements.txt
```

You need a Google GenAI API key (free from [Google AI Studio](https://aistudio.google.com/apikey)).
Two ways to provide it — pick one:

**Option A — `.env` file (recommended, no re-typing every session)**

1. Copy the example file and rename it:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and paste in your real key:
   ```
   GEMINI_API_KEY=your-actual-key-here
   ```
3. That's it. `code_reviewer.py` calls `load_dotenv()` on startup, which
   reads `.env` automatically. `.env` is already listed in `.gitignore`,
   so it will never get committed or uploaded if you push this to GitHub.

**Option B — environment variable (no file, resets each new terminal)**

```bash
export GEMINI_API_KEY="your-actual-key-here"      # Mac/Linux
set GEMINI_API_KEY=your-actual-key-here            # Windows CMD
$env:GEMINI_API_KEY="your-actual-key-here"         # Windows PowerShell
```

⚠️ Never paste your real key directly into `code_reviewer.py` or commit
it to version control — treat it like a password.

## Usage

```bash
python code_reviewer.py sample_buggy.py
python code_reviewer.py path/to/App.java --model gemini-2.0-flash
```

Supported file types: `.py`, `.js`, `.java`.

## Files

- `code_reviewer.py` — the full CLI tool.
- `sample_buggy.py` — a small sample file with an intentional bug
  (calls an undefined `transform()` and assumes `item.active` always exists)
  to test the tool against.
- `requirements.txt` — dependencies (`google-generativeai`, `rich`, `python-dotenv`).
- `.env.example` — template showing the expected `.env` format. Copy to
  `.env` and fill in your real key.
- `.gitignore` — makes sure your real `.env` (and your real key) never
  gets committed if you push this project to Git.
