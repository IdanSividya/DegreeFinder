from typing import List, Protocol, Dict, Any
from backend.core.models import Program
from backend.core.rules import AndRule
from backend.core.rule_factory import RuleFactory

class ProgramRepository(Protocol):
    def list_programs(self) -> List[Program]:
        ...

class JsonProgramRepository:
    def __init__(self, programs_json: Any, factory: RuleFactory):
        self.programs_json = programs_json
        self.factory = factory

    def list_programs(self) -> List[Program]:
        programs: List[Program] = []
        for p in self.programs_json:
            rules = [self.factory.from_json(r) for r in p.get("rules", [])]
            programs.append(Program(
                id=p["id"],
                name=p["name"],
                faculty=p.get("faculty", ""),
                rules=[AndRule(*rules)]
            ))
        return programs
