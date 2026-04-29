import json
from typing import List, Dict, Any
from .clients import chat_client
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
    """Generate a code modification blueprint using a flagship LLM."""
    try:
        response = chat_client.chat.completions.create(
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
        
    except Exception as e:
        return [{"error": str(e)}]

