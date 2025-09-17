# backend/institutions/huji/loaders.py
import json
import os
from typing import Any, Dict, List

def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_subjects(root: str) -> Dict[str, Any]:
    return _read_json(os.path.join(root, "subjects.json"))

def load_policy(root: str) -> Dict[str, Any]:
    return _read_json(os.path.join(root, "policy.json"))

def load_programs(root: str) -> List[Dict[str, Any]]:
    return _read_json(os.path.join(root, "programs.json"))
