from llmlingua import PromptCompressor
import torch
class Compressor():
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.llm_lingua = PromptCompressor(
            "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
            use_llmlingua2=True, 
            device_map=self.device
            )

    def compress_prompt(self,text):
        print("------------------------------------------------------------------------------------------------")
        print(f"Using Device: {self.device}")
        token_count = len(text.split())
        rate = 1.0 if token_count <= 20 else 0.7 if token_count <= 35 else 0.6 if token_count <= 50 else 0.5
        print(f"Tokens: {token_count}, Rate: {rate}")
        result = self.llm_lingua.compress_prompt(text, rate=rate)
        print(f"Stats: {result['origin_tokens']} --> {result['compressed_tokens']} tokens ({result['ratio']})")
        print("------------------------------------------------------------------------------------------------")
        return result['compressed_prompt']