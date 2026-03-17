# memory.py — session-safe version
from collections import defaultdict

_histories: dict = defaultdict(list)

def add_message(session_id: str, role: str, content: str):
    _histories[session_id].append({"role": role, "content": content})

def get_history(session_id: str):
    return _histories[session_id][-6:]