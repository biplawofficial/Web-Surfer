import asyncio
import json
import sys
from typing import List, Dict, Any, Optional

from ollama import AsyncClient as OllamaAsyncClient
from playwright.async_api import async_playwright, Page
from pydantic import BaseModel


# --- Data Models ---
class Action(BaseModel):
    action: str
    element_id: Optional[int] = None
    text: Optional[str] = None
    url: Optional[str] = None
    key: Optional[str] = None
    direction: Optional[str] = None  # for scroll: 'up', 'down'


class ActionPlan(BaseModel):
    thinking: str
    actions: List[Action]


# --- Agent Class ---
class WebAgent:
    def __init__(self, model: str = "gpt-oss:120b-cloud"):
        self.model = model
        self.client = OllamaAsyncClient(timeout=30.0)
        self.element_map: Dict[
            int, Any
        ] = {}  # Stores element details for the current page

    async def _get_llm_response(self, prompt: str, system_prompt: str) -> str:
        """Call Ollama with retry logic."""
        for attempt in range(3):
            try:
                response = await self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    options={"temperature": 0.2},
                )
                return response.message.content
            except Exception as e:
                print(f"LLM Error (Attempt {attempt + 1}): {e}")
                await asyncio.sleep(1)
        return "{}"

    def _parse_json(self, text: str) -> Dict:
        """Robust JSON extraction."""
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end != -1:
                return json.loads(text[start:end])
            return json.loads(text)
        except json.JSONDecodeError:
            print("Failed to parse JSON")
            return {}

    async def extract_interactive_elements(self, page: Page) -> str:
        """
        Injects JS to find interactive elements, assigns them IDs, and returns a text representation.
        Also populates self.element_map with bounding boxes / selectors if needed (simplifying to just tracking existence).
        """
        js_script = """
        () => {
            // Remove old labels
            document.querySelectorAll('.agent-label').forEach(el => el.remove());
            
            let items = [];
            let idCounter = 1;
            
            // Define interesting elements
            const selectors = [
                'a[href]', 'button', 'input', 'textarea', 'select', 
                '[role="button"]', '[onclick]',
                'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'span', 'div'
            ];
            
            document.querySelectorAll(selectors.join(',')).forEach(el => {
                // Check visibility
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden') {
                    
                    // Filter out empty text nodes for non-interactive elements
                    const isInteractive = ['A', 'BUTTON', 'INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.hasAttribute('role') || el.hasAttribute('onclick');
                    let text = el.innerText || el.placeholder || el.value || el.name || el.getAttribute('aria-label') || '';
                    text = text.replace(/\\s+/g, ' ').trim();
                    
                    if (!isInteractive && (text.length < 3 || text.length > 1000)) return; // Skip noise
                    
                    // Assign explicit ID attribute for Playwright
                    const uniqueId = idCounter++;
                    el.setAttribute('data-agent-id', uniqueId);
                    
                    // Add visual label
                    const label = document.createElement('div');
                    label.className = 'agent-label';
                    label.innerText = uniqueId;
                    label.style.position = 'absolute';
                    label.style.background = isInteractive ? 'yellow' : 'lightblue'; // Distinguish text
                    label.style.color = 'black';
                    label.style.border = '1px solid black';
                    label.style.zIndex = '10000';
                    label.style.top = (window.scrollY + rect.top) + 'px';
                    label.style.left = (window.scrollX + rect.left) + 'px';
                    if (!isInteractive) label.style.opacity = '0.5'; // Less intrusive for text
                    document.body.appendChild(label);
                    
                    items.push({
                        id: uniqueId,
                        tag: el.tagName.toLowerCase(),
                        text: text.slice(0, 1000)
                    });
                }
            });
            return items;
        }
        """
        try:
            elements = await page.evaluate(js_script)

            # Build text representation for LLM
            lines = []
            for el in elements:
                tag = el["tag"]
                text = el["text"]
                lines.append(f"[{el['id']}] {tag}: {text}")

            return "\n".join(lines)
        except Exception:
            return "Page is reloading or unavailable."

    async def plan(self, goal: str, element_text: str, url: str) -> ActionPlan:
        system_prompt = """You are a web automation agent with DOM grounding.
You see the page as a list of elements (Interactive & Text), each with a unique ID [N].
Your goal is to navigate and act to achieve the specific user request.

CRITICAL RULES:
1. INTERACT ONLY via IDs: Use `click_element` or `type_element` with the ID from the list.
2. READ TEXT: Look at the text content of elements to find the answer.
3. ITERATIVE: Perform 1-2 actions at a time, then wait to see the result.
4. SCROLL: If you don't see what you need, use `scroll` to see more.
5. ANSWER: Extract the answer from the page content if visible.
6. FINISH: Only finish when the specific answer is found and stated in the `text` field.

Response JSON Format:
{
    "thinking": "Reasoning...",
    "actions": [
        {"action": "click_element", "element_id": 12},
        {"action": "type_element", "element_id": 5, "text": "iphone 17 pro"},
        {"action": "scroll", "direction": "down"},
        {"action": "go_back"},
        {"action": "wait", "text": "2000"},
        {"action": "finish", "text": "The price is $999."}
    ]
}
"""
        user_prompt = f"""
GOAL: {goal}
CURRENT URL: {url}
VISIBLE ELEMENTS:
{element_text}
"""
        response_text = await self._get_llm_response(user_prompt, system_prompt)
        data = self._parse_json(response_text)

        if not data or "actions" not in data:
            return ActionPlan(thinking="Parsing failed or empty response", actions=[])

        return ActionPlan(**data)

    async def execute_plan(self, page: Page, plan: ActionPlan):
        print(f"🤖 Thinking: {plan.thinking}")

        for action in plan.actions:
            try:
                # --- Navigation ---
                if action.action == "goto" and action.url:
                    print(f"  -> Going to {action.url}")
                    await page.goto(action.url)
                    await page.wait_for_load_state("domcontentloaded")
                    return False, ""  # Re-plan

                # --- Element Interactions ---
                elif action.action == "click_element" and action.element_id:
                    print(f"  -> Clicking ID [{action.element_id}]")
                    selector = f'[data-agent-id="{action.element_id}"]'
                    try:
                        await page.wait_for_selector(
                            selector, state="visible", timeout=5000
                        )
                        await page.click(selector)
                        await self._wait_for_stable(page)
                    except Exception as e:
                        print(f"    Failed to click {action.element_id}: {e}")

                elif action.action == "type_element" and action.element_id:
                    print(f"  -> Typing '{action.text}' into ID [{action.element_id}]")
                    selector = f'[data-agent-id="{action.element_id}"]'
                    try:
                        await page.wait_for_selector(
                            selector, state="visible", timeout=5000
                        )
                        await page.fill(selector, action.text or "")
                        await page.keyboard.press("Enter")  # Usually implies submit
                        await self._wait_for_stable(page)
                    except Exception as e:
                        print(f"    Failed to type in {action.element_id}: {e}")

                # --- Page Actions ---
                elif action.action == "scroll":
                    direction = action.direction or "down"
                    print(f"  -> Scrolling {direction}")
                    delta_y = 500 if direction == "down" else -500
                    await page.mouse.wheel(0, delta_y)
                    await asyncio.sleep(1)  # Wait for valid layout

                elif action.action == "go_back":
                    print("  -> Going back")
                    await page.go_back()
                    await self._wait_for_stable(page)

                elif action.action == "wait":
                    delay = int(action.text or 1000)
                    await asyncio.sleep(delay / 1000)

                elif action.action == "finish":
                    print(f"✅ Finished: {action.text}")
                    return True, action.text

            except Exception as e:
                print(f"  ❌ Action failed: {action.action} - {e}")

        return False, ""

    async def _wait_for_stable(self, page: Page):
        """Wait for page to accept input/load."""
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
            await page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass  # Timeout is okay, we just move on

    async def run(self, goal: str):
        result = {"status": "failed", "answer": "", "log": []}
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            try:
                # Start at search engine if not a URL
                if not goal.startswith("http"):
                    await page.goto("https://duckduckgo.com")
                else:
                    await page.goto(goal)

                steps = 0
                max_steps = 20

                while steps < max_steps:
                    steps += 1
                    try:
                        # 1. Grounding (Observe)
                        element_text = await self.extract_interactive_elements(page)
                        url = page.url

                        # 2. Plan
                        plan = await self.plan(goal, element_text, url)
                        result["log"].append(
                            {"step": steps, "plan": plan.dict(), "url": url}
                        )

                        # 3. Execute
                        done, answer = await self.execute_plan(page, plan)
                        if done:
                            result["status"] = "success"
                            result["answer"] = answer
                            break

                        await asyncio.sleep(1)

                    except Exception as e:
                        print(f"Loop Error: {e}")
                        result["error"] = str(e)
                        break

                if steps >= max_steps:
                    print("⚠️ Max steps reached.")
                    result["status"] = "max_steps_reached"

            finally:
                await browser.close()
        return result


# --- Main Entry ---
async def main():
    agent = WebAgent()
    if len(sys.argv) > 1:
        goal = " ".join(sys.argv[1:])
    else:
        goal = (
            input("Target Goal: ") or "Search for the latest Agentic AI news on Google"
        )

    result = await agent.run(goal)

    if result["status"] == "success":
        print("\n✨ FINAL ANSWER ✨")
        print(result["answer"])
    else:
        print("\n❌ Task Failed or Incomplete")
        # print(json.dumps(result, indent=2)) # Hiding verbose log
        if result.get("error"):
            print(f"Error: {result['error']}")
        else:
            print("Could not complete the task within step limit.")


if __name__ == "__main__":
    asyncio.run(main())
