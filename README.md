# 🌐 Agentic-Surfer

An AI web browsing agent. Give it a question or a task, it opens a real browser, navigates the web, and gets it done — autonomously.

---

## How It Works

The agent runs a simple **observe → plan → execute** loop:

1. **Observe** — Scrapes all interactive elements (buttons, links, inputs) from the page using Playwright and assigns each a numbered ID
2. **Plan** — Sends the element list + page text + user query to an LLM (via Ollama), which picks a tool to use next
3. **Execute** — Runs the chosen tool (click, type, scroll, etc.)
4. **Repeat** — Loops until the LLM calls `answer` (for questions) or `done` (for action tasks)

### Available Tools

| Tool          | Params               | Description                       |
| ------------- | -------------------- | --------------------------------- |
| `click`       | `element_id`         | Click an element                  |
| `type`        | `element_id`, `text` | Type into an input field          |
| `goto`        | `url`                | Open a URL                        |
| `scroll_down` | —                    | Scroll down                       |
| `scroll_up`   | —                    | Scroll up                         |
| `go_back`     | —                    | Go to previous page               |
| `answer`      | `text`               | Return text answer, close browser |
| `done`        | `text`               | Task complete, keep browser open  |

---

## Project Structure

```
Agentic-Surfer/
├── backend/
│   ├── main.py            # FastAPI server (POST /query on port 8007)
│   ├── multi_task.py       # Core agent — observe, plan, execute loop
│   ├── requirements.txt    # Python dependencies
│   └── LICENSE
├── frontend/
│   └── Browser-controller/ # React frontend (Vite)
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- [Ollama](https://ollama.com/) running locally
- Playwright Chromium

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
```

**Run the API server:**

```bash
python main.py
# POST http://localhost:8007/query → {"query": "...", "mode": 1}
```

**Run via CLI:**

```bash
python multi_task.py
# Enter your query when prompted
```

### Frontend Setup

```bash
cd frontend/Browser-controller
npm install
npm run dev
```

---

## Config

| Setting     | File                    | Default                   |
| ----------- | ----------------------- | ------------------------- |
| LLM model   | `backend/multi_task.py` | `gpt-oss:120b-cloud`      |
| Max steps   | `backend/multi_task.py` | `20`                      |
| Server port | `backend/main.py`       | `8007`                    |
| Headless    | `backend/multi_task.py` | `False` (visible browser) |

---

## License

MIT
