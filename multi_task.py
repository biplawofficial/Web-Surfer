import asyncio
import json
import re
import random
import time
from dataclasses import dataclass
from typing import Any, List, Dict, Tuple
from pydantic import BaseModel
from ollama import AsyncClient as OllamaAsyncClient
from playwright.async_api import async_playwright, Page, Browser

class Action(BaseModel):
    action: str
    selector: str | None = None
    url: str | None = None
    text: str | None = None
    limit: int | None = None
    key: str | None = None
    delay: int | None = None

class ActionPlan(BaseModel):
    actions: List[Action]
    reasoning: str | None = None

@dataclass
class EnhancedLLMAgent:
    model: str = "gpt-oss:20b-cloud"
    host: str | None = None
    
    async def reason_and_plan(self, context: Dict, current_observation: Dict, original_goal: str) -> Tuple[ActionPlan, str]:
        try:
            client = OllamaAsyncClient(host=self.host, timeout=30.0)
            system_prompt = """You are an expert web automation assistant. Respond with VALID JSON only.
1. For shopping queries, ALWAYS start with Amazon India (amazon.in)
2. Never suggest Flipkart - use Amazon or Google only
Response format: {"reasoning": "explanation", "actions": [{"action": "goto", "url": "https://amazon.in"}]}"""

            user_message = f"GOAL: {original_goal}\nCURRENT: {current_observation.get('url','')}\nTITLE: {current_observation.get('title','')}\nSTEP: {len(context.get('history',[]))+1}"

            response = await client.chat(model=self.model, messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ], options={"temperature": 0.3})
            
            content = response.message.content.strip()
            json_content = self._extract_json(content)
            plan_data = json.loads(json_content)
            action_plan = ActionPlan(**plan_data)
            return action_plan, plan_data.get("reasoning", "Planning next steps...")
            
        except Exception as e:
            return self._get_fallback_plan(original_goal, current_observation), f"Fallback: {e}"

    def _extract_json(self, content: str) -> str:
        try: return content if json.loads(content) else content
        except: pass
        
        patterns = [r'\{[^{}]*\{[^{}]*\}[^{}]*\}', r'\{[^{}]*\}']
        for pattern in patterns:
            for match in re.findall(pattern, content, re.DOTALL):
                try:
                    cleaned = self._clean_json(match)
                    json.loads(cleaned)
                    return cleaned
                except: continue
        
        try:
            start = content.find('{')
            if start != -1:
                brace_count = 0
                for i, char in enumerate(content[start:]):
                    if char == '{': brace_count += 1
                    elif char == '}': 
                        brace_count -= 1
                        if brace_count == 0:
                            json_str = content[start:start+i+1]
                            cleaned = self._clean_json(json_str)
                            json.loads(cleaned)
                            return cleaned
        except: pass
        
        return self._default_json()

    def _clean_json(self, s: str) -> str:
        s = re.sub(r'\n\s*', ' ', s)
        s = re.sub(r',\s*}', '}', s)
        s = re.sub(r',\s*]', ']', s)
        s = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', s)
        return s

    def _default_json(self) -> str:
        return '{"reasoning": "Using fallback navigation plan", "actions": [{"action": "goto", "url": "https://www.amazon.in"}, {"action": "wait", "delay": 4000}]}'

    def _get_fallback_plan(self, goal: str, observation: Dict) -> ActionPlan:
        goal_lower = goal.lower()
        if any(word in goal_lower for word in ['laptop', 'phone', 'buy', 'shopping', 'price', 'amazon']):
            return ActionPlan(
                actions=[
                    Action(action="goto", url="https://www.amazon.in"),
                    Action(action="wait", delay=4000),
                    Action(action="type", selector="#twotabsearchtextbox", text=goal, delay=100),
                    Action(action="wait", delay=1000),
                    Action(action="click", selector="#nav-search-submit-button"),
                    Action(action="wait", delay=5000),
                    Action(action="extract", selector="[data-component-type='s-search-result'] h2 a span", key="products", limit=8)
                ],
                reasoning="Amazon India shopping fallback"
            )
        else:
            return ActionPlan(
                actions=[
                    Action(action="goto", url="https://www.google.com"),
                    Action(action="wait", delay=4000),
                    Action(action="type", selector="input[name='q'], textarea[name='q'], input[title='Search']", text=goal, delay=80),
                    Action(action="wait", delay=1500),
                    Action(action="press_key", key="Enter"),
                    Action(action="wait", delay=5000),
                    Action(action="extract", selector="h3", key="search_results", limit=8)
                ],
                reasoning="Google search fallback"
            )

    async def extract_final_data(self, content: str, original_goal: str):
        prompt = f"""
        Extract structured data from the web browsing results based on the user's original goal.
        Original goal: {original_goal}
        Browsing results: {content[:1500]}
        
        Return ONLY valid JSON without any additional text.
        """
        return await self.call_llm(prompt)

    async def call_llm(self, prompt: str):
        try:
            client = OllamaAsyncClient(host=self.host, timeout=30.0)
            system_prompt = """Return ONLY valid JSON without any additional text."""
            
            response = await client.chat(model=self.model, messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ], options={"temperature": 0.1})
            
            content = response.message.content.strip()
            json_content = self._extract_json(content)
            return json.loads(json_content)
            
        except Exception as e:
            return {"error": f"Failed to extract final data: {e}"}

class EnhancedWebAgent:
    def __init__(self, model: str = "gpt-oss:20b-cloud"):
        self.llm_agent = EnhancedLLMAgent(model=model)
        self.max_steps = 8
        self.context = {'history': [], 'original_goal': '', 'achieved_goal': False}
    
    async def _setup_browser(self, playwright_instance):
        browser = await playwright_instance.chromium.launch(
            headless=False,
            args=['--no-sandbox']
        )
        
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        page.set_default_timeout(20000)
        return browser, page
    
    async def _human_like_delay(self, min_sec=1, max_sec=4):
        await asyncio.sleep(random.uniform(min_sec, max_sec))
    
    async def run_enhanced_loop(self, user_prompt: str):
        self.context['original_goal'] = user_prompt
        
        async with async_playwright() as p:
            browser, page = await self._setup_browser(p)
            
            step = 0
            consecutive_failures = 0
            
            while step < self.max_steps and not self.context['achieved_goal']:
                step += 1
                
                try:
                    observation = await self._observe(page)
                    action_plan, _ = await self.llm_agent.reason_and_plan(self.context, observation, user_prompt)
                    result = await self._execute_plan(page, action_plan)
                    
                    if await self._check_success(page, result, observation, user_prompt):
                        self.context['achieved_goal'] = True
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        if consecutive_failures >= 3:
                            break
                    
                    self.context['history'].append({
                        'step': step,
                        'url': page.url
                    })
                    
                    await self._human_like_delay(2, 4)
                    
                except Exception as e:
                    consecutive_failures += 1
                    await asyncio.sleep(3)
                    if consecutive_failures >= 3:
                        break
            
            final_content = await self._collect_results(page)
            structured_data = await self.llm_agent.extract_final_data(str(final_content), user_prompt)
            
            await browser.close()
            
            return {
                "query": user_prompt,
                "results": structured_data
            }
    
    async def _execute_plan(self, page: Page, action_plan: ActionPlan) -> Dict:
        results = {}
        for action in action_plan.actions:
            try:
                if action.action == "goto" and action.url:
                    await page.goto(action.url, wait_until="domcontentloaded")
                    await self._human_like_delay(2, 3)
                elif action.action == "click" and action.selector:
                    element = await page.wait_for_selector(action.selector, timeout=10000)
                    if element:
                        await element.click()
                        await self._human_like_delay(1, 2)
                elif action.action == "type" and action.selector and action.text:
                    element = await page.wait_for_selector(action.selector, timeout=5000)
                    if element:
                        await element.click()
                        await element.fill("")
                        await element.type(action.text, delay=100)
                        await self._human_like_delay(0.5, 1)
                elif action.action == "press_key" and action.key:
                    await page.keyboard.press(action.key)
                    await self._human_like_delay(1, 2)
                elif action.action == "extract" and action.selector:
                    await self._human_like_delay(2)
                    elements = await page.query_selector_all(action.selector)
                    extracted = []
                    for el in elements[:action.limit or 10]:
                        try:
                            text = await el.text_content()
                            if text and len(text.strip()) > 3:
                                extracted.append(text.strip()[:200])
                        except: continue
                    if action.key and extracted:
                        results[action.key] = extracted
                elif action.action == "wait":
                    delay = action.delay or 2000
                    await asyncio.sleep(delay/1000)
            except:
                continue
        return results
    
    async def _check_success(self, page: Page, result: Dict, observation: Dict, goal: str) -> bool:
        try:
            extracted_items = []
            for key, value in result.items():
                if isinstance(value, list) and len(value) > 0:
                    extracted_items.extend(value)
            return len(extracted_items) >= 3
        except:
            return False
    
    async def _observe(self, page: Page) -> Dict:
        try:
            return {"url": page.url, "title": await page.title()}
        except:
            return {"url": page.url, "title": "Error"}
    
    async def _collect_results(self, page: Page) -> Dict:
        try:
            data = await page.evaluate("""
                () => ({
                    products: Array.from(document.querySelectorAll('[data-component-type="s-search-result"] h2 a span')).map(e => e.textContent?.trim()).filter(Boolean).slice(0,8),
                    search_results: Array.from(document.querySelectorAll('h3')).map(e => e.textContent?.trim()).filter(Boolean).slice(0,8),
                    headings: Array.from(document.querySelectorAll('h1, h2, h3')).map(e => e.textContent?.trim()).filter(Boolean).slice(0,8)
                })
            """)
            return {"url": page.url, "extracted_data": data}
        except:
            return {"url": page.url, "extracted_data": {}}

async def main():
    # Ask user for input
    user_prompt = input("Enter your web task: ").strip()
    if not user_prompt:
        user_prompt = "laptops under 50000 on Amazon"
    
    agent = EnhancedWebAgent()
    results = await agent.run_enhanced_loop(user_prompt)
    
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())