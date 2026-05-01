"""
Tests for :mod:`core.planner` — blueprint generation via LLM.

The chat client is mocked by the global ``conftest.py``, so no real LLM
call is made.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.planner import generate_blueprint, BlueprintError


class TestGenerateBlueprint:
    def test_returns_list_of_changes(self, mock_chat_client: MagicMock):
        """A successful call should return a list of change dictionaries."""
        result = generate_blueprint("add logging", "file: app.py")
        assert isinstance(result, list)
        assert len(result) >= 1
        change = result[0]
        assert "file" in change
        assert "action" in change
        assert change["action"] in ("create", "modify", "delete", "rename")

    def test_handles_dict_with_blueprint_key(self, mock_chat_client: MagicMock):
        """When the LLM returns ``{\"blueprint\": [...]}``, the function
        should extract the list."""
        def blueprint_response(*args, **kwargs):
            return MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content=(
                                '{"blueprint": [{"file": "a.py", '
                                '"action": "modify", "description": "x", '
                                '"logic": "y"}]}'
                            ),
                            refusal=None,
                        )
                    )
                ]
            )
        mock_chat_client.chat.completions.create = blueprint_response
        result = generate_blueprint("task", "context")
        assert isinstance(result, list)
        assert result[0]["file"] == "a.py"

    def test_handles_single_object(self, mock_chat_client: MagicMock):
        """When the LLM returns a single object (not a list), the function
        should wrap it in a list."""
        def single_response(*args, **kwargs):
            return MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content=(
                                '{"file": "a.py", "action": "create", '
                                '"description": "x", "logic": "y"}'
                            ),
                            refusal=None,
                        )
                    )
                ]
            )
        mock_chat_client.chat.completions.create = single_response
        result = generate_blueprint("task", "context")
        assert isinstance(result, list)
        assert result[0]["file"] == "a.py"

    def test_raises_on_llm_failure(self, mock_chat_client: MagicMock):
        """When the LLM call fails, :class:`BlueprintError` should be raised."""
        def failing_chat(*args, **kwargs):
            raise RuntimeError("LLM down")
        mock_chat_client.chat.completions.create = failing_chat
        with pytest.raises(BlueprintError, match="LLM down"):
            generate_blueprint("task", "context")
