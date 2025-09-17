from typing import List, Dict
from backend.core.models import Applicant, Program, EligibilityResult
from backend.core.repositories import ProgramRepository

class EligibilityEngine:
    def __init__(self, repo: ProgramRepository, policy):
        self.repo = repo
        self.policy = policy

    def _compute_D_safe(self, applicant: Applicant):
        # יש מוסדות (כמו BGU) שאין להם compute_D_with_breakdown
        compute_D = getattr(self.policy, "compute_D_with_breakdown", None)
        if callable(compute_D):
            d_val, _notes = compute_D(applicant.bagrut)
            return float(d_val)
        return None

    def evaluate_applicant(self, applicant: Applicant) -> List[EligibilityResult]:
        results: List[EligibilityResult] = []
        programs = self.repo.list_programs()

        d_value = self._compute_D_safe(applicant)
        p_value = applicant.psychometric.total

        for prog in programs:
            explanations: List[str] = []
            passed_all = True
            s_value = None
            threshold_value = None

            # כל תוכנית מכילה AndRule אחד מחובר מכללי ה־JSON
            for rule in prog.rules:
                rr = rule.evaluate(applicant)
                explanations.append(rr.explanation)
                if rr.passed is False:
                    passed_all = False
                if "S=" in rr.explanation:
                    try:
                        s_str = rr.explanation.split("S=")[1].split(" ")[0]
                        s_value = float(s_str)
                    except Exception:
                        s_value = None
                if "threshold=" in rr.explanation:
                    try:
                        thr_str = rr.explanation.split("threshold=")[1].split(")")[0]
                        threshold_value = float(thr_str)
                    except Exception:
                        threshold_value = None

            details: Dict[str, float] = {"P": float(p_value)}
            if d_value is not None:
                details["D"] = float(d_value)
            if s_value is not None:
                details["S"] = s_value
            if threshold_value is not None:
                details["threshold"] = threshold_value

            results.append(EligibilityResult(
                program=prog,
                passed=passed_all,
                explanations=explanations,
                details=details
            ))
        return results
