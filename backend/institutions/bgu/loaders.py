import json
import os
from typing import Any, Dict, List

def _read(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_subjects(root: str) -> Dict[str, Any]:
    return _read(os.path.join(root, "subjects.json"))

def load_policy(root: str) -> Dict[str, Any]:
    return _read(os.path.join(root, "policy.json"))

def load_programs(root: str) -> List[Dict[str, Any]]:
    return _read(os.path.join(root, "programs.json"))
