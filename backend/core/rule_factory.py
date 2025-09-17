from typing import Dict, Any, Optional

from backend.core.rules import (
    AndRule,
    SubjectRequirementRule,
    TechnionSakemThresholdRule,
    HujiSakemThresholdRule,
    BguSakemThresholdRule,
)
from backend.institutions.technion.policy import TechnionPolicy
from backend.institutions.huji.policy import HujiPolicy
from backend.institutions.bgu.policy import BguPolicy


class RuleFactory:
    """
    Build a single rule from a JSON rule config.
    The repository calls: factory.from_json(rule_cfg)
    """

    def __init__(
        self,
        institution: str,
        technion_policy: Optional[TechnionPolicy] = None,
        huji_policy: Optional[HujiPolicy] = None,
        bgu_policy: Optional[BguPolicy] = None,
    ) -> None:
        self.institution = (institution or "").lower()
        self.technion_policy = technion_policy
        self.huji_policy = huji_policy
        self.bgu_policy = bgu_policy

    def from_json(self, rule_cfg: Dict[str, Any]):
        rtype = (rule_cfg.get("type") or "").lower()

        # 1) דרישת מקצוע (יח"ל/ציון)
        if rtype == "subject_requirement":
            return SubjectRequirementRule(
                subject=rule_cfg["subject"],
                min_units=int(rule_cfg["min_units"]),
                min_score=rule_cfg.get("min_score"),
            )

        # 2) סכם (שונה לכל מוסד)
        if rtype == "sakem_threshold":
            thr = float(rule_cfg["threshold"])
            if self.institution == "technion":
                return TechnionSakemThresholdRule(policy=self.technion_policy, threshold=thr)
            if self.institution == "huji":
                return HujiSakemThresholdRule(policy=self.huji_policy, threshold=thr)
            if self.institution == "bgu":
                return BguSakemThresholdRule(policy=self.bgu_policy, threshold=thr)

        raise ValueError(f"Unknown rule type or institution not wired: {rule_cfg!r} / {self.institution}")
