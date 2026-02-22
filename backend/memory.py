import json
import os

MEMORY_FILE = "memory.json"

class Memory:
    def __init__(self):
        self.history = self.load()

    def load(self):
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        return []

    def save(self):
        with open(MEMORY_FILE, "w") as f:
            json.dump(self.history, f)

    def add(self, role, content):
        self.history.append({"role": role, "content": content})
        self.save()

    def format_for_prompt(self):
        formatted = ""
        for msg in self.history:
            formatted += f"{msg['role'].capitalize()}: {msg['content']}\n"
        return formatted