"""Unit tests for conversation memory (window logic, no LLM calls)."""
from memory import ConversationMemory


def test_keeps_recent_turns_within_window():
    mem = ConversationMemory(window=4)
    mem.add("user", "hi")
    mem.add("assistant", "hello")
    ctx = mem.context()
    assert "user: hi" in ctx
    assert "assistant: hello" in ctx
    assert mem.summary == ""  # nothing folded yet


def test_context_is_empty_initially():
    assert ConversationMemory().context() == ""
