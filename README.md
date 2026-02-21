# 🌐 Agentic-Surfer

An AI-powered autonomous web browsing agent. Give it a natural-language question or task, it launches a **real Chromium browser**, navigates the web, interacts with pages, and returns the result — all by itself.

---

## 🎯 What It Does

- **Ask a question** → the agent Googles it, reads pages, and brings you the answer.
- **Give it a task** → e.g. "Play Lo-fi hip hop on YouTube", and it opens the browser, searches, clicks play, and leaves the browser open for you.
- Everything happens in a **visible browser window** so you can watch the agent work in real-time.

---

## 🏗 Architecture & Full Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend                          │
│              (Vite + React 19, port 5173)                   │
│                                                             │
│  User types query ──► POST /query ──► FastAPI Backend       │
│  Agent response   ◄── JSON result ◄── FastAPI Backend       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Server                            │
│               (main.py — port 8007)                         │
│                                                             │
│  Accepts POST /query with {query, mode}                     │
│  Calls run_agent(query) from multi_task.py                  │
│  Returns JSON: {status, answer}                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Agent Loop (multi_task.py)                 │
│                                                             │
│  For up to 20 steps:                                        │
│    1. OBSERVE  — scrape page elements via Playwright        │
│    2. PLAN     — send state to LLM, get next tool call      │
│    3. EXECUTE  — run the tool (click, type, scroll, etc.)   │
│    4. REPEAT   — until LLM calls "answer" or "done"         │
│                                                             │
│  Browser: Playwright Chromium (headless=False)              │
│  LLM:     Ollama AsyncClient (gpt-oss:120b-cloud)          │
│  Search:  DuckDuckGo as default start page                  │
└─────────────────────────────────────────────────────────────┘
```

### Step-by-step flow:

1. **User** types a query in the React chat UI (e.g. _"What is the price of iPhone 16?"_)
2. **Frontend** sends a `POST` request to `http://localhost:8007/query` with `{ "query": "...", "mode": 1 }`
3. **FastAPI** (`main.py`) receives the request and calls `run_agent(query)` from `multi_task.py`
4. **Agent** launches a visible Chromium browser via Playwright
5. If the query is a URL, it navigates directly; otherwise it starts at **DuckDuckGo**
6. **Observe-Plan-Execute loop** begins (max 20 iterations):
   - `scrape_elements()` finds all visible interactive elements (links, buttons, inputs) and assigns each a numeric `data-id`
   - `get_page_text()` extracts the first 2000 chars of visible body text
   - `ask_llm()` sends all of this + action history to the LLM and gets back a single JSON tool call
   - `run_tool()` executes the action on the page
7. When the LLM decides the task is complete, it calls:
   - `"answer"` → returns the text answer and **closes** the browser
   - `"done"` → returns a message and **keeps** the browser open for the user
8. **FastAPI** returns `{ "status": "success", "answer": "..." }` to the frontend
9. **Frontend** displays the response in the chat

---

## 🧰 Available Tools (Agent Actions)

These are the tools the LLM can invoke on each step:

| Tool          | Params               | Description                                            |
| ------------- | -------------------- | ------------------------------------------------------ |
| `click`       | `element_id`         | Click an interactive element by its scraped ID         |
| `type`        | `element_id`, `text` | Type text into an input field and press Enter          |
| `goto`        | `url`                | Navigate to a specific URL                             |
| `scroll_down` | —                    | Scroll the page down by 500px                          |
| `scroll_up`   | —                    | Scroll the page up by 500px                            |
| `go_back`     | —                    | Navigate to the previous page                          |
| `answer`      | `text`               | Return a text answer to the user and close the browser |
| `done`        | `text`               | Mark task complete and keep the browser open           |

---

## 📂 Project Structure

```
Agentic-Surfer/
├── backend/
│   ├── main.py              # FastAPI server — single POST /query endpoint
│   ├── multi_task.py         # Core agent logic — observe/plan/execute loop
│   ├── requirements.txt      # Python dependencies
│   └── LICENSE               # MIT License
├── frontend/
│   ├── index.html            # Standalone HTML chat (backup/demo)
│   └── Browser-controller/   # React + Vite frontend
│       ├── src/
│       │   ├── main.jsx      # React entry point (StrictMode + createRoot)
│       │   ├── App.jsx       # Chat component (messages, input, API calls)
│       │   ├── App.css       # Chat-specific styles (bubbles, layout)
│       │   └── index.css     # Global reset + centering
│       ├── index.html        # Vite HTML template
│       ├── package.json      # Dependencies (React 19, Vite 7)
│       └── vite.config.js    # Vite config
└── README.md
```

---

## 🔍 Internal Code Details

### `backend/main.py` — API Server

- Uses **FastAPI** with CORS middleware (`allow_origins=["*"]` for local dev)
- Defines a `QueryRequest` Pydantic model: `{ query: str, mode: int = 1 }`
- Single endpoint: `POST /query` → calls `run_agent(query)` and returns JSON
- Runs on **port 8007** via **uvicorn**

### `backend/multi_task.py` — Agent Core

#### Tool Registry (`TOOLS`)

- 8 tools defined as dicts with `name`, `desc`, `params`
- Formatted into a text block that becomes part of the system prompt

#### `scrape_elements(page)`

- Runs JavaScript in the page via `page.evaluate()`
- Selects all `a, button, input, textarea, select, [role="button"]` elements
- Filters out zero-size (invisible) elements
- Extracts text from `innerText`, `placeholder`, `value`, or `aria-label`
- Assigns each element a `data-id` attribute (1, 2, 3, …)
- Returns a numbered text list like: `1 -> button: "Search"`

#### `get_page_text(page)`

- Extracts the `innerText` of `<body>`, collapses whitespace, and truncates to **2000 characters**

#### `ask_llm(client, model, query, page_text, elements, url)`

- Constructs a prompt with: user query, current URL, page content, interactive elements, action history
- Sends to the LLM via **Ollama AsyncClient** with `temperature=0.1` for deterministic responses
- Parses the JSON tool call from the LLM response (extracts first `{...}` block)
- Appends every LLM response to a global `history` list to prevent loops

#### `run_tool(page, action)`

- Executes the tool using Playwright:
  - `click` → `page.click('[data-id="N"]')` with 5s timeout
  - `type` → `page.fill()` + `keyboard.press("Enter")` with 5s timeout
  - `goto` → `page.goto(url)` with 10s timeout
  - `scroll_down` / `scroll_up` → `page.mouse.wheel()` by ±500px
  - `go_back` → `page.go_back()`
  - `answer` / `done` → returns a signal to stop the loop
- Catches all exceptions so one failed action doesn't crash the agent

#### `run_agent(query, model)`

- Launches a **non-headless** Chromium browser via Playwright
- If the query is a URL, navigates directly; otherwise starts at DuckDuckGo
- Runs the observe→plan→execute loop for up to **20 steps**
- Handles tab switching (if new tabs are opened, switches to the latest)
- Handles page crashes (re-opens a new tab if `PAGE_CLOSED` is detected)
- Returns `{ "status": "success"/"failed", "answer": "..." }`

#### Agent Rules (in system prompt)

1. Respond with ONLY a single JSON object
2. Use exactly ONE tool per response
3. Use `answer` for questions, `done` for action tasks
4. Stop immediately once task is achieved
5. Never repeat the same action twice in a row
6. Don't scroll more than 3-4 times
7. If no result found, change strategy

### `frontend/Browser-controller/src/App.jsx` — Chat UI

- React functional component with `useState` for messages, input, loading
- Messages rendered as a scrollable list with auto-scroll on new messages
- User messages: black bubble (right-aligned); Agent messages: grey bubble (left-aligned)
- Animated 3-dot typing indicator while waiting for the API
- Sends `POST` to `http://localhost:8007/query` with `{ query, mode: 1 }`
- Handles response fields: `data.answer`, `data.result`, `data.status`
- Graceful error handling for network failures

---

## 🚀 Getting Started (Clone to Running)

### Prerequisites

| Requirement | Version | Purpose             |
| ----------- | ------- | ------------------- |
| Python      | 3.9+    | Backend runtime     |
| Node.js     | 18+     | Frontend dev server |
| Ollama      | latest  | Local LLM inference |
| Git         | any     | Clone the repo      |

### 1. Clone the Repository

```bash
git clone https://github.com/biplawofficial/Agentic-Surfer.git
cd Agentic-Surfer
```

### 2. Backend Setup

```bash
# Navigate to backend
cd backend

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate          # Linux/Mac
# or: venv\Scripts\activate       # Windows

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright's Chromium browser
playwright install chromium
```

### 3. Start Ollama

Make sure [Ollama](https://ollama.com/) is installed and running. The agent uses the model `gpt-oss:120b-cloud` by default. Pull it if needed:

```bash
ollama pull gpt-oss:120b-cloud
```

### 4. Run the Backend API Server

```bash
cd backend
python main.py
# Server starts at http://localhost:8007
# Endpoint: POST /query  →  Body: {"query": "your question", "mode": 1}
```

### 5. Frontend Setup & Run

```bash
# Open a NEW terminal
cd frontend/Browser-controller

# Install Node dependencies
npm install

# Start the dev server
npm run dev
# Frontend starts at http://localhost:5173
```

### 6. Use It

1. Open **http://localhost:5173** in your browser
2. Type a question or task in the chat input
3. Watch the agent open a Chromium browser and autonomously browse the web
4. The response appears in the chat when the agent finishes

### Alternative: CLI Mode (No Frontend)

```bash
cd backend
python multi_task.py
# Enter your query when prompted
```

---

## ⚙️ Configuration

| Setting          | File                    | Default                   | Notes                            |
| ---------------- | ----------------------- | ------------------------- | -------------------------------- |
| LLM model        | `backend/multi_task.py` | `gpt-oss:120b-cloud`      | Change in `run_agent()` param    |
| Max steps        | `backend/multi_task.py` | `20`                      | `range(1, 21)` in the agent loop |
| Server port      | `backend/main.py`       | `8007`                    | Change in `uvicorn.run()`        |
| Frontend API URL | `frontend/.../App.jsx`  | `http://localhost:8007`   | Change the `fetch()` URL         |
| Headless mode    | `backend/multi_task.py` | `False` (visible browser) | Change in `pw.chromium.launch()` |
| LLM temperature  | `backend/multi_task.py` | `0.1`                     | Lower = more deterministic       |
| Scroll amount    | `backend/multi_task.py` | `500px`                   | Change in `page.mouse.wheel()`   |
| Page text limit  | `backend/multi_task.py` | `2000 chars`              | Truncation in `get_page_text()`  |

---

## 📦 Dependencies

### Backend (Python)

| Package         | Purpose                                      |
| --------------- | -------------------------------------------- |
| `fastapi`       | REST API framework                           |
| `uvicorn`       | ASGI server for FastAPI                      |
| `pydantic`      | Request/response data validation             |
| `ollama`        | Python client for Ollama LLM inference       |
| `playwright`    | Browser automation (Chromium)                |
| `requests`      | HTTP requests                                |
| `llmlingua`     | LLM prompt compression (optional utility)    |
| `torch`         | PyTorch (required by llmlingua)              |
| `transformers`  | Hugging Face transformers (req by llmlingua) |
| `accelerate`    | Model acceleration library                   |
| `sentencepiece` | Tokenizer for certain models                 |
| `protobuf`      | Serialization library                        |

### Frontend (Node.js)

| Package                | Purpose                 |
| ---------------------- | ----------------------- |
| `react` (19.2)         | UI library              |
| `react-dom`            | React DOM renderer      |
| `vite` (7.3)           | Build tool & dev server |
| `@vitejs/plugin-react` | React plugin for Vite   |
| `eslint`               | Code linting            |

---

## 📄 License

MIT
