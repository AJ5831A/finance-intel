import pytest


class MockLLM:
    """Stand-in for the Gemini client. Pop responses in FIFO order.

    Each queued item is the object generate_structured should return.
    """

    def __init__(self):
        self.queue = []
        self.calls = []
        self.text_queue = []
        self.text_calls = []

    def queue_response(self, obj):
        self.queue.append(obj)

    def queue_text(self, text):
        self.text_queue.append(text)

    def generate_structured(self, schema, prompt, **kwargs):
        self.calls.append({"schema": schema, "prompt": prompt})
        if not self.queue:
            raise AssertionError("MockLLM queue empty; queue a response in the test")
        return self.queue.pop(0)

    def generate_text(self, prompt, **kwargs):
        self.text_calls.append({"prompt": prompt})
        if not self.text_queue:
            return "stub answer"
        return self.text_queue.pop(0)


@pytest.fixture
def mock_llm():
    return MockLLM()
