import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

class LLM:
    def __init__(self, model="llama3"):
        self.model = model

    def generate(self, prompt, temperature=0.8, max_tokens=800):
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
        )
        return response.json()["response"]
    
class MemoryManager:
    def __init__(self):
           self.summary = ""
           self.message_count =0

    async def update_summary(self, messages, llm):
        summary_prompt = f"""
        Summarize the important context from this conversation briefly:


        {messages}
        """
        response = await llm.generate(summary_prompt)
        self.summary = response
        self.message_count = 0