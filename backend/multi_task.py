import asyncio
import json
from ollama import AsyncClient
from playwright.async_api import async_playwright

# ── Tools ────────────────────────────────────────────────────────────
history = []
TOOLS = [
    {"name": "click", "desc": "Click an element", "params": ["element_id"]},
    {
        "name": "type",
        "desc": "Type into an input field",
        "params": ["element_id", "text"],
    },
    {"name": "goto", "desc": "Open a URL", "params": ["url"]},
    {"name": "scroll_down", "desc": "Scroll the page down", "params": []},
    {"name": "scroll_up", "desc": "Scroll the page up", "params": []},
    {"name": "go_back", "desc": "Go to the previous page", "params": []},
    {
        "name": "answer",
        "desc": "Return a text answer and close browser",
        "params": ["text"],
    },
    {
        "name": "done",
        "desc": "Task complete, keep browser open for user",
        "params": ["text"],
    },
]


def tools_as_text():
    lines = []
    for t in TOOLS:
        p = ", ".join(t["params"]) if t["params"] else "none"
        lines.append(f"  - {t['name']}({p}): {t['desc']}")
    return "\n".join(lines)


# ── Page Helpers ─────────────────────────────────────────────────────


async def scrape_elements(page):
    """Find interactive elements, assign IDs, return a readable map."""
    try:
        elements = await page.evaluate("""() => {
            const results = [];
            let id = 1;
            document.querySelectorAll('a, button, input, textarea, select, [role="button"]').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;
                const text = (el.innerText || el.placeholder || el.value || el.getAttribute('aria-label') || '').trim();
                if (!text) return;
                el.setAttribute('data-id', id);
                results.push({ id: id, tag: el.tagName.toLowerCase(), text: text.slice(0, 80) });
                id++;
            });
            return results;
        }""")
        lines = [f'{e["id"]} -> {e["tag"]}: "{e["text"]}"' for e in elements]
        return "\n".join(lines) if lines else "No interactive elements found."
    except Exception:
        return "PAGE_CLOSED"


async def get_page_text(page):
    """Get visible text from the page body."""
    try:
        text = await page.inner_text("body")
        return " ".join(text.split())[:2000]
    except Exception:
        return ""


# ── LLM ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are a web browsing assistant. You have these tools:
{tools_as_text()}

RULES:
1. Respond with ONLY a single JSON object. No extra text.
2. Use exactly ONE tool per response.
3. Use "answer" when the user asked a QUESTION and you found the answer. This closes the browser.
4. Use "done" when the user asked you to DO something (play a song, open a page, open a PDF).
   This keeps the browser open so the user can see/use it.
5. STOP immediately once the task is achieved. Don't keep clicking after a song starts or a page loads.
6. Never repeat the exact same action twice in a row.
7. Dont scroll for too long max 3-4 times.
8. If you dont find any result change the logic.

Examples:
{{"tool": "type", "params": {{"element_id": 5, "text": "AI news"}}}}
{{"tool": "click", "params": {{"element_id": 3}}}}
{{"tool": "answer", "params": {{"text": "The price is $799."}}}}
{{"tool": "done", "params": {{"text": "The song is now playing."}}}}"""


async def ask_llm(client, model, query, page_text, elements, url):
    """Send page state to the LLM and get next action as JSON."""
    prompt = (
        f"User query: {query}\n"
        f"Current URL: {url}\n\n"
        f"Page content:\n{page_text}\n\n"
        f"Interactive elements:\n{elements}\n\n"
        f"History:\n{history}\n\n"
        f"What tool should I use next? Respond with JSON only."
    )
    try:
        resp = await client.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.1},
        )
        text = resp.message.content
        history.append(text)
        return json.loads(text[text.find("{") : text.rfind("}") + 1])
    except Exception as e:
        print(f"  LLM error: {e}")
        return None


# ── Tool Executor ────────────────────────────────────────────────────


async def run_tool(page, action):
    """Execute one tool. Returns (signal, text) or (None, None)."""
    tool = action.get("tool", "")
    p = action.get("params", {})

    try:
        if tool == "click":
            await page.click(f'[data-id="{p["element_id"]}"]', timeout=5000)
            await page.wait_for_load_state("domcontentloaded", timeout=3000)

        elif tool == "type":
            await page.fill(
                f'[data-id="{p["element_id"]}"]', p.get("text", ""), timeout=5000
            )
            await page.keyboard.press("Enter")
            await page.wait_for_load_state("domcontentloaded", timeout=3000)

        elif tool == "goto":
            await page.goto(p.get("url", ""), timeout=10000)

        elif tool == "scroll_down":
            await page.mouse.wheel(0, 500)
            await asyncio.sleep(0.5)

        elif tool == "scroll_up":
            await page.mouse.wheel(0, -500)
            await asyncio.sleep(0.5)

        elif tool == "go_back":
            await page.go_back(timeout=5000)

        elif tool == "answer":
            return "answer", p.get("text", "Done.")

        elif tool == "done":
            return "done", p.get("text", "Done.")

    except Exception as e:
        print(f"  Tool failed: {e}")

    return None, None


# ── Main Agent Loop ──────────────────────────────────────────────────


async def run_agent(query, model="gpt-oss:120b-cloud"):
    client = AsyncClient(timeout=30.0)
    global history
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        start = query if query.startswith("http") else "https://duckduckgo.com"
        await page.goto(start)
        print(f"🌐 Starting at {start}\n")

        for step in range(1, 21):
            print(f"── Step {step} ──")

            # Switch to newest tab if a new one was opened
            if len(context.pages) > 1:
                page = context.pages[-1]

            # 1. Observe
            elements = await scrape_elements(page)

            # If the page died, open a fresh one
            if elements == "PAGE_CLOSED":
                print("  ⚠ Page closed, opening new tab...")
                page = await context.new_page()
                await page.goto("https://duckduckgo.com")
                continue

            page_text = await get_page_text(page)

            # 2. Plan
            action = await ask_llm(client, model, query, page_text, elements, page.url)
            if not action:
                print("  ⚠ No action, retrying...")
                continue

            print(f"  🛠  {action.get('tool')}  {action.get('params', {})}")

            # 3. Execute
            signal, text = await run_tool(page, action)

            if signal == "answer":
                print(f"\n✅ {text}")
                await browser.close()
                history = []
                return {"status": "success", "answer": text}

            if signal == "done":
                print(f"\n✅ {text}")
                print("🌐 Browser left open. Press Enter to close...")
                await asyncio.get_event_loop().run_in_executor(None, input)
                await browser.close()
                history = []
                return {"status": "success", "answer": text}

            await asyncio.sleep(1)

        print("\n⚠️ Hit step limit.")
        await browser.close()
        return {"status": "failed", "answer": "Could not find the answer in time."}


# ── CLI Entry ────────────────────────────────────────────────────────


async def main():
    query = input("Enter your query: ")
    result = await run_agent(query)
    print(f"\nResult: {result['answer']}")


if __name__ == "__main__":
    asyncio.run(main())
