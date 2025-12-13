import asyncio
import requests
import json
from playwright.sync_api import sync_playwright
import time
import random
import re
class Helper():
    def __init__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=VizDisplayCompositor',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding'
            ]
        )
        user_agents = [
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        self.context = self.browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=random.choice(user_agents),
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        self.page = self.context.new_page()
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            })
        """)
    def save_results(self):
        try:
            with open("results_log.txt", "a") as f:
                f.write(f"URL: {self.page.url}\n")
                f.write(f"Title: {self.page.title()}\n")
                f.write(f"Content Preview: {self.extract_visible_content()[:500]}\n")
                f.write("="*50 + "\n")
            return "Results saved to results_log.txt"
        except Exception as e:
            return f"Error saving results: {e}"
    def human_like_delay(self, min_sec=1, max_sec=4):
        base_delay = random.uniform(min_sec, max_sec)
        chunks = max(1, int(base_delay))
        for _ in range(chunks):
            time.sleep(base_delay / chunks)
            if random.random() > 0.7:
                time.sleep(random.uniform(0.1, 0.3))

    def human_like_mouse_movement(self):
        try:

            for _ in range(3):
                x = random.randint(100, 1200)
                y = random.randint(100, 600)
                self.page.mouse.move(x, y)
                time.sleep(0.2)
        except:
            pass
    
    def search_google_safely(self, query: str):
        try:
            print(f"🔍 Searching for: {query}")
            self.page.goto("https://www.wikipedia.org", wait_until="networkidle")
            self.human_like_delay(1, 2)
            self.page.goto("https://www.google.com", wait_until="networkidle")
            self.human_like_delay(1, 3)
            search_box = "textarea[name='q'], input[name='q']"
            self.page.wait_for_selector(search_box, timeout=10000)
            self.page.click(search_box)
            self.human_like_delay(0.5, 1)
            for i, char in enumerate(query):
                self.page.type(search_box, char, delay=random.randint(80, 200))
                if random.random() > 0.9:
                    self.human_like_delay(0.1, 0.4)
                if i % 5 == 0:
                    self.human_like_mouse_movement()
            self.human_like_delay(1, 2)
            self.page.press(search_box, "Enter")
            self.human_like_delay(1, 4)
            content = self.page.content().lower()
            if any(blocked in content for blocked in ["unusual traffic", "detected unusual traffic", "captcha"]):
                print("🚫 Blocked by Google. Trying alternative approach...")
                return self.use_alternative_search_engine(query)
            
            return self.get_page_info()
        except Exception as e:
            return {"error": str(e)}
    
    def use_alternative_search_engine(self, query: str):
        alternatives = [
            ("https://search.yahoo.com", "input[name='p']"),
            ("https://duckduckgo.com", "input[name='q']"),
            ("https://www.bing.com", "input[name='q']"),
        ]
        for url, selector in alternatives:
            try:
                self.page.goto(url, wait_until="networkidle")
                self.page.fill(selector, query)
                self.page.press(selector, "Enter")
                return self.get_page_info()
            except:
                continue
        return {"error": "All search engines blocked"}
    
    def smart_click(self, target: str):
        strategies = [
            f"a:has-text('{target}')",
            f"h3:has-text('{target}')",
            f"div:has-text('{target}')",
            f"span:has-text('{target}')",
            f"button:has-text('{target}')",
            f"a:has-text(/:.*{target}.*/i)",
            f"h3:has-text(/:.*{target}.*/i)",
        ]
        
        for selector in strategies:
            try:
                if self.page.locator(selector).count() > 0:
                    self.human_like_mouse_movement()
                    self.page.click(selector)
                    self.human_like_delay(1, 2)
                    if self.page.url != self.page.context.pages[0].url:
                        return self.get_page_info()
            except:
                continue
        return "Click failed - element not found"

    def extract_visible_content(self):
        try:
            content = self.page.evaluate("""
                () => {
                    const elementsToRemove = document.querySelectorAll('script, style, nav, footer, header');
                    elementsToRemove.forEach(el => el.remove());
                    return document.body.innerText;
                }
            """)
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            clean_content = '\n'.join(lines[:100])
            return clean_content[:2000]
        except Exception as e:
            return f"Extraction error: {e}" 
    def get_page_info(self):
        try:
            return {
                "url": self.page.url,
                "title": self.page.title(),
                "content_preview": self.extract_visible_content()[:500]
            }
        except:
            return {"error": "Could not get page info"}
    
    def close(self):
        self.browser.close()
        self.playwright.stop()

    def clear_cookies_and_cache(self):
        """Clear cookies and cache between sessions"""
        try:
            self.context.clear_cookies()
            # Add storage cleanup if needed
            self.page.evaluate("() => localStorage.clear()")
            self.page.evaluate("() => sessionStorage.clear()")
        except:
            pass

    def rotate_user_agent(self):
        """Rotate user agent for new sessions"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        ]
        new_agent = random.choice(user_agents)
        self.context.set_extra_http_headers({'User-Agent': new_agent})
