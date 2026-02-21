# 🌐 Agentic-Surfer

An AI agent that opens a real browser, navigates the web, and completes tasks autonomously — just give it a natural-language query.

## How It Works

The agent runs an **observe → plan → execute** loop:

1. **Observe** — Scrapes interactive elements (buttons, links, inputs) from the page using Playwright
2. **Plan** — Sends page state + query to an LLM (via Ollama), which picks the next action
3. **Execute** — Runs the action (click, type, scroll, navigate, etc.)
4. **Repeat** — Loops until the task is done (max 20 steps)

### Tools

| Tool                        | Description                            |
| --------------------------- | -------------------------------------- |
| `click`                     | Click an element                       |
| `type`                      | Type into an input and press Enter     |
| `goto`                      | Navigate to a URL                      |
| `scroll_down` / `scroll_up` | Scroll the page                        |
| `go_back`                   | Go to previous page                    |
| `answer`                    | Return an answer and close the browser |
| `done`                      | Mark task complete, keep browser open  |

## Project Structure

```
Agentic-Surfer/
├── backend/
│   ├── main.py           # FastAPI server (POST /query, port 8007)
│   ├── multi_task.py     # Agent core — observe/plan/execute loop
│   └── requirements.txt
├── frontend/
│   └── Browser-controller/  # React + Vite chat UI
│       └── src/
│           ├── App.jsx      # Chat component
│           └── App.css      # Styles
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- [Ollama](https://ollama.com/) installed and running

### Setup & Run

```bash
# Clone
git clone https://github.com/biplawofficial/Agentic-Surfer.git
cd Agentic-Surfer

# Backend
cd backend
pip install -r requirements.txt
playwright install chromium
python main.py                 # Starts API on http://localhost:8007

# Frontend (new terminal)
cd frontend/Browser-controller
npm install
npm run dev                    # Starts UI on http://localhost:5173
```

Open **http://localhost:5173**, type a query, and watch the agent browse the web for you.

### CLI Mode

```bash
cd backend
python multi_task.py
```

## Config

| Setting     | Default              | Where                                 |
| ----------- | -------------------- | ------------------------------------- |
| LLM model   | `gpt-oss:120b-cloud` | `multi_task.py` → `run_agent()`       |
| Max steps   | 20                   | `multi_task.py` → agent loop          |
| Server port | 8007                 | `main.py` → `uvicorn.run()`           |
| Headless    | `False`              | `multi_task.py` → `chromium.launch()` |

## License

MIT
