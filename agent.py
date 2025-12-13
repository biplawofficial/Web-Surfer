import ollama
import re

class mainLLM:
    def __init__(self):
        self.model = "llama3.1:8b"
    
    def call_llm(self, prompt: str):
        try:
            response = ollama.generate(model=self.model, prompt=prompt)
            result = response['response']
            return result
        except Exception as e:
            return f"Error: {e}"
    
    def get_action_plan(self, user_input: str, available_tools: str):
        prompt = f"""
        you have access to those tools for web navigation and data extraction from the browser environment:
        {available_tools}
        User wants to: {user_input}
        Create a complete web navigation plan To get the required information from the web. Return ONLY JSON:
        {{
            "goal": "{user_input}",
            "steps": [
                {{  
                    "order": 1,
                    "action": "search_google_safely",
                    "query": "search query",
                    "description": "What to look for in the search results"
                }},
                {{
                    "order": 2,
                    "action": "click_result", 
                    "target": "which result to click",
                    "description": "navigate to specific site"
                }},
                {{
                    "order": 3,
                    "action": "extract_data",
                    "what": "what information to extract",
                    "description": "final data extraction"
                }}
                ... and so on up to 7 steps max.
            ]
        }}
        note:
        -The target in the click_result should be an element that should be available on the page after the search or an element that is likely to be present on the page.
        -make use of save_results action to store intermediate results if needed.
        -You should even go to new page and again search for something else if needed to achieve the goal.
        Keep it to min 3-7 steps max. Be specific about search queries and targets.
        """
        return self.call_llm(prompt)
    
    def extract_final_data(self, content: str, original_goal: str):
        """Final call to extract structured data"""
        prompt = f"""
        - You are an very useful agent that gives structured outputs as strict json structure to users.
        - Prompt by user (Original goal): {original_goal}
        - Resutls we have by browsing the web: {content[:1500]}
        - This will be the last output that will be directly given to the user based on the question and the response collected from the web.
          so make sure you create proper json out of this thing okay.
          The content in the json structure result field should be humanized properly okay 
          so the structure is{{"input":{original_goal}, "output":{content[:500]}(should be properly humanized dont provide unstructured data please)}}
        - Please dont write anythign else in the ouput i just want you to give me the json  with input and output field the output must be humanized as per the resutls obtained from the web
        """
        #return 
        return self.call_llm(prompt)
