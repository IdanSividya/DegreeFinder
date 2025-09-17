from typing import Protocol, Optional
from backend.core.models import Applicant, RuleResult
from backend.institutions.technion.policy import TechnionPolicy

class AdmissionRule(Protocol):
    def evaluate(self, applicant: Applicant) -> RuleResult:
        ...

class SubjectRequirementRule:
    def __init__(self, subject: str, min_units: int, min_score: Optional[float] = None):
        self.subject = subject
        self.min_units = min_units
        self.min_score = min_score

    def evaluate(self, applicant: Applicant) -> RuleResult:
        s = applicant.bagrut.find(self.subject)
        if s is None:
            return RuleResult(False, f"{self.subject}: missing")
        if s.units < self.min_units:
            return RuleResult(False, f"{self.subject}: units {s.units} < required {self.min_units}")
        if self.min_score is not None:
            if s.score < self.min_score:
                return RuleResult(False, f"{self.subject}: score {s.score} < required {self.min_score}")
        return RuleResult(True, f"{self.subject} OK (units={s.units}, score={s.score})")

class TechnionSakemThresholdRule:
    def __init__(self, policy: TechnionPolicy, threshold: float):
        self.policy = policy
        self.threshold = threshold

    def evaluate(self, applicant: Applicant) -> RuleResult:
        d, d_notes = self.policy.compute_D_with_breakdown(applicant.bagrut)
        p = applicant.psychometric.total
        s = 0.5 * d + 0.075 * p - 19.0
        if s >= self.threshold:
            return RuleResult(True, f"S={s:.2f} ≥ threshold={self.threshold}")
        return RuleResult(False, f"S={s:.2f} < threshold={self.threshold}")

class AndRule:
    def __init__(self, *rules):
        self.rules = list(rules)

    def evaluate(self, applicant: Applicant) -> RuleResult:
        explanations = []
        for r in self.rules:
            rr = r.evaluate(applicant)
            explanations.append(rr.explanation)
            if rr.passed is False:
                return RuleResult(False, " | ".join(explanations))
        return RuleResult(True, " | ".join(explanations))
