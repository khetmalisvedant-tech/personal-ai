import httpx
import json


class Engine:
    def __init__(self, model: str = "llama3", temperature: float = 0.7):
        self.model = model
        self.temperature = temperature
        self.base_url = "http://localhost:11434/api/generate"

    async def generate(self, prompt: str):
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": self.temperature,
            "stream": True
        }

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", self.base_url, json=payload) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            continue