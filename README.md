# 🌐 Agentic-Surfer

An AI-powered **autonomous web browsing agent** that can navigate websites, read page content, and answer questions — all on its own. Built with Python, FastAPI, Playwright, and Ollama.

Give it a goal like _"What is the latest news in AI?"_ and watch it open a browser, search DuckDuckGo, click through results, read content, and return the answer.

---

## 🧠 How It Works

Agentic-Surfer uses an **Observe → Plan → Execute** loop powered by an LLM:

```
User Goal → Launch Browser → [Observe DOM → Plan Actions → Execute] × N → Return Answer
```

1. **Observe** — JavaScript is injected into the page to extract all visible elements (links, buttons, inputs, text). Each element gets a unique numbered ID and a visual label overlay on the page.

2. **Plan** — The extracted element list, current URL, and user goal are sent to an LLM (via Ollama). The LLM reasons about what to do next and outputs a JSON action plan.

3. **Execute** — The agent carries out the planned actions using Playwright:
   - `click_element` — Click on a numbered element
   - `type_element` — Type text into an input field (+ auto-submit)
   - `scroll` — Scroll up or down to reveal more content
   - `go_back` — Navigate back
   - `wait` — Pause briefly
   - `finish` — Return the final answer

4. **Loop** — Steps 1–3 repeat (up to 20 iterations) until the LLM issues a `finish` action with the answer.

---

## � Project Structure

```
Agentic-Surfer/
├── main.py              # FastAPI server — exposes POST /query endpoint
├── multi_task.py         # Core WebAgent — browser automation + LLM planning
├── requirements.txt      # Python dependencies
├── package.json          # (placeholder)
├── LICENSE               # MIT License
└── README.md
```

| File               | Description                                                                                                                    |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `main.py`          | FastAPI server on port **8007**. Accepts `{ "query": "...", "mode": 1 }` via `POST /query` and runs the `WebAgent`.            |
| `multi_task.py`    | The `WebAgent` class: launches Chromium, runs the observe-plan-execute loop, and talks to the LLM. Also has a CLI entry point. |
| `requirements.txt` | All Python dependencies (FastAPI, Playwright, Ollama, PyTorch, Transformers, etc.).                                            |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+**
- **[Ollama](https://ollama.com/)** installed and running locally with the `gpt-oss:120b-cloud` model (or update the model name in `multi_task.py`)
- **Chromium** browser for Playwright

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/your-username/Agentic-Surfer.git
cd Agentic-Surfer

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install Playwright's Chromium browser
playwright install chromium
```

### Running

**Option 1 — API Server:**

```bash
python main.py
```

The server starts on `http://0.0.0.0:8007`. Send queries via POST:

```bash
curl -X POST http://localhost:8007/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the latest news in AI?", "mode": 1}'
```

**Option 2 — CLI Mode:**

```bash
python multi_task.py "What is the latest news in AI?"
```

Or run without arguments to enter the goal interactively:

```bash
python multi_task.py
# → Target Goal: <type your goal here>
```

> **Note:** The browser launches in **visible (non-headless) mode** so you can watch the agent navigate in real time.

---

## ⚙️ Configuration

| Setting                | Location                 | Default                    |
| ---------------------- | ------------------------ | -------------------------- |
| LLM Model              | `multi_task.py` line 28  | `gpt-oss:120b-cloud`       |
| Max Steps              | `multi_task.py` line 269 | `20`                       |
| Server Port            | `main.py` line 38        | `8007`                     |
| Browser Mode           | `multi_task.py` line 254 | `headless=False` (visible) |
| Fallback Search Engine | `multi_task.py` line 264 | DuckDuckGo                 |

---

## � Key Features

- **Autonomous Web Navigation** — The agent browses the web by itself, clicking links, filling forms, and scrolling pages.
- **DOM Grounding** — Elements are identified by injected IDs, giving the LLM precise control over what to click/type.
- **Visual Element Labels** — Interactive elements get yellow overlays; text elements get blue overlays on the page for debugging.
- **LLM-Driven Planning** — Each step is reasoned about with chain-of-thought (`thinking` field) before acting.
- **Retry Logic** — LLM calls have 3 retries with exponential backoff.
- **Robust JSON Parsing** — Extracts JSON from LLM responses even if surrounded by extra text.
- **DuckDuckGo Fallback** — Automatically starts searches from DuckDuckGo when no URL is provided.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
