from typing import Any
from backend.core.rules import SubjectRequirementRule, TechnionSakemThresholdRule
from backend.institutions.technion.policy import TechnionPolicy

class RuleFactory:
    def __init__(self, institution: str, technion_policy: TechnionPolicy = None):
        self.institution = institution
        self.technion_policy = technion_policy

    def from_json(self, cfg: Any):
        rule_type = cfg.get("type")
        if self.institution == "technion":
            if rule_type == "subject_requirement":
                return SubjectRequirementRule(
                    subject=cfg["subject"],
                    min_units=int(cfg["min_units"]),
                    min_score=cfg.get("min_score")
                )
            if rule_type == "sakem_threshold":
                return TechnionSakemThresholdRule(
                    policy=self.technion_policy,
                    threshold=float(cfg["threshold"])
                )
        raise ValueError(f"Unsupported rule: {cfg}")
