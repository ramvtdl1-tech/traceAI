"""Limits and session-memory validation for the public demo; no disk storage."""

import re
import threading
import time
from collections import deque
from uuid import uuid4


class RequestBudget:
    """A bounded sliding window shared by all sessions in one server process."""

    def __init__(self, limit=200, window_seconds=3600, clock=time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self.clock = clock
        self.requests = deque()
        self.lock = threading.Lock()

    def claim(self):
        with self.lock:
            now = self.clock()
            while self.requests and self.requests[0] <= now - self.window:
                self.requests.popleft()
            if len(self.requests) >= self.limit:
                return False
            self.requests.append(now)
            return True


def bounded_history(messages, max_messages=40, max_chars=24000):
    """Keep recent context within both bounds, starting on a user turn."""
    selected = []
    size = 0
    for message in reversed(messages):
        if len(selected) >= max_messages or size + len(message["content"]) > max_chars:
            break
        selected.append(dict(message))
        size += len(message["content"])
    selected.reverse()
    while selected and selected[0]["role"] != "user":
        selected.pop(0)
    return selected


def memory_candidates(candidates, existing):
    """Require explicit approval for every new, non-sensitive memory."""
    def normalized(content):
        return re.sub(r"\W+", " ", content.casefold()).strip()

    seen = {normalized(m["content"]) for m in existing}
    result = []
    for item in candidates[:10]:
        content = item.get("content", "").strip()
        key = normalized(content)
        if not key or len(content) > 500 or key in seen or item.get("sensitivity") != "normal":
            continue
        seen.add(key)
        result.append({"id": str(uuid4()), "content": content, "status": "pending"})
    return result
