from typing import Protocol, Optional
from backend.core.models import Applicant, RuleResult
from backend.institutions.technion.policy import TechnionPolicy

# HUJI may not be present at import-time during bootstrap; keep your existing guard.
try:
    from backend.institutions.huji.policy import HujiPolicy
except Exception:
    HujiPolicy = object  # type: ignore

# BGU policy import (חדש)
try:
    from backend.institutions.bgu.policy import BguPolicy
except Exception:
    BguPolicy = object  # type: ignore


class AdmissionRule(Protocol):
    def evaluate(self, applicant: Applicant) -> RuleResult: ...


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
        if self.min_score is not None and s.score < self.min_score:
            return RuleResult(False, f"{self.subject}: score {s.score} < required {self.min_score}")
        return RuleResult(True, f"{self.subject} OK (units={s.units}, score={s.score})")


class TechnionSakemThresholdRule:
    def __init__(self, policy: TechnionPolicy, threshold: float):
        self.policy = policy
        self.threshold = float(threshold)

    def evaluate(self, applicant: Applicant) -> RuleResult:
        # D from policy; P from applicant; S computed by technion formula inside this rule
        d, _ = self.policy.compute_D_with_breakdown(applicant.bagrut)
        p = applicant.psychometric.total
        s = 0.5 * d + 0.075 * p - 19.0
        passed = s >= self.threshold
        return RuleResult(passed, f"S={s:.3f} {'≥' if passed else '<'} threshold={self.threshold}")


class HujiSakemThresholdRule:
    def __init__(self, policy: HujiPolicy, threshold: float):
        self.policy = policy
        self.threshold = float(threshold)

    def evaluate(self, applicant: Applicant) -> RuleResult:
        # HUJI computes S דרך ה־policy (כולל נרמולים ועיגול כפי שמוגדר שם)
        d, _ = self.policy.compute_D_with_breakdown(applicant.bagrut)
        p = applicant.psychometric.total
        s = self.policy.compute_sechem(d, p)  # HUJI: S מחושב בפוליסי
        passed = s >= self.threshold
        return RuleResult(passed, f"S={s:.3f} {'≥' if passed else '<'} threshold={self.threshold}")


class BguSakemThresholdRule:
    """
    BGU: ה־policy מחשב ממוצע בגרות אופטימלי עם בונוסים (תקרה 120),
    מבצע נרמול B = 650 + 10*(avg-100), ואז S = (B + P)/2.
    כאן אנו רק קוראים ל־policy כדי לקבל S, ומחזירים הסבר בפורמט שה־engine שלך כבר מפרש.
    """
    def __init__(self, policy: BguPolicy, threshold: float):
        self.policy = policy
        self.threshold = float(threshold)

    def evaluate(self, applicant: Applicant) -> RuleResult:
        details, _explanations = self.policy.compute_sakem(applicant)
        s = float(details.get("S", 0.0))
        passed = s >= self.threshold
        return RuleResult(passed, f"S={s:.3f} {'≥' if passed else '<'} threshold={self.threshold}")


class AndRule:
    def __init__(self, *rules):
        self.rules = list(rules)

    def evaluate(self, applicant: Applicant) -> RuleResult:
        exps = []
        for r in self.rules:
            rr = r.evaluate(applicant)
            exps.append(rr.explanation)
            if not rr.passed:
                return RuleResult(False, " | ".join(exps))
        return RuleResult(True, " | ".join(exps))
