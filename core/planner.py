import json
from typing import List, Dict, Any
from .clients import get_chat_client
from .config import settings

PLANNING_PROMPT = """
You are a senior software architect. Given a task and the relevant code context, output a strict JSON blueprint of the exact changes needed.

The output must be a JSON array of objects, where each object has:
- "file": The relative path to the file to modify.
- "action": One of ["create", "modify", "delete", "rename"].
- "description": A concise description of the logic to implement.
- "logic": The actual code or pseudocode for the change.

Do NOT include any markdown formatting or explanations outside the JSON.
"""

def generate_blueprint(task: str, context: str) -> List[Dict[str, Any]]:
    """Generate a code modification blueprint using a flagship LLM.

    Returns:
        A list of change dictionaries representing the blueprint.

    Raises:
        BlueprintError: If the LLM call fails or returns unparseable output.
    """
    client = get_chat_client()
    try:
        response = client.chat.completions.create(
            model=settings.chat.model_name,
            messages=[
                {"role": "system", "content": PLANNING_PROMPT},
                {"role": "user", "content": f"Task: {task}\n\nContext:\n{context}"}
            ],
            response_format={"type": "json_object"}
        )

        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)

        # Expecting a list or a dict with a "blueprint" key
        if isinstance(data, dict) and "blueprint" in data:
            return data["blueprint"]
        if isinstance(data, list):
            return data
        return [data]

    except json.JSONDecodeError as e:
        raise BlueprintError(f"Failed to parse LLM response as JSON: {e}") from e
    except Exception as e:
        raise BlueprintError(f"LLM call failed: {e}") from e


class BlueprintError(Exception):
    """Raised when blueprint generation fails."""
    pass

