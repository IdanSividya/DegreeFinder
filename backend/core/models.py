from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class SubjectGrade:
    name: str
    units: int
    score: float

@dataclass
class BagrutRecord:
    subjects: List[SubjectGrade] = field(default_factory=list)

    def find(self, name: str) -> Optional[SubjectGrade]:
        for s in self.subjects:
            if s.name == name:
                return s
        return None

@dataclass
class PsychometricScore:
    total: int

@dataclass
class Applicant:
    bagrut: BagrutRecord
    psychometric: PsychometricScore

@dataclass
class RuleResult:
    passed: bool
    explanation: str

@dataclass
class Program:
    id: str
    name: str
    faculty: str
    rules: List[Any]  # AdmissionRule at runtime

@dataclass
class EligibilityResult:
    program: Program
    passed: bool
    explanations: List[str]
    details: Dict[str, float]
