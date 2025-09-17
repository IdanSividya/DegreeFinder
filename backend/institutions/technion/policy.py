# backend/institutions/technion/policy.py
from typing import Dict, Any, Tuple, List
from backend.core.models import BagrutRecord, SubjectGrade

class TechnionPolicy:
    """
    Same logic as the original code:
    - Mandatory subjects included (optionally drop Jewish Philosophy if Literature >= 2u, when present)
    - Mathematics has double weight
    - Electives are added greedily ONLY if they improve the weighted average,
      and we stop once we reach >= min_total_units (if possible)
    - Bonuses are applied PER SUBJECT (base 4u/5u and extra for 5u categories)
    - Cap D at max_D
    """
    def __init__(self, policy_cfg: Dict[str, Any], subjects_catalog: Dict[str, Any]):
        self.cfg = policy_cfg
        self.subjects_catalog = subjects_catalog
        self.double_weight_subjects = set(policy_cfg.get("double_weight_subjects", []))
        self.min_total_units = int(policy_cfg.get("min_total_units", 20))
        self.max_D = float(policy_cfg.get("max_D", 119.0))
        self.allow_drop = policy_cfg.get("allow_drop_jewish_philosophy_if", None)

        self.bonus_base = policy_cfg.get("bonus_base", {})
        self.min_score_for_bonus = float(self.bonus_base.get("min_score", 60))
        self.base_bonus_4u = float(self.bonus_base.get("4u", 10))
        self.base_bonus_5u = float(self.bonus_base.get("5u", 20))

        self.bonus_extra = policy_cfg.get("bonus_extra", {})
        self.extra_math_5u = float(self.bonus_extra.get("math_5u", 30))
        self.extra_scientific_5u = float(self.bonus_extra.get("scientific_5u", 25))
        self.extra_technological_5u = float(self.bonus_extra.get("technological_5u", 25))
        self.extra_aggregate_bump = float(self.bonus_extra.get("aggregate_bump", 30))
        self.scientific_set = set(self.bonus_extra.get("scientific_set", []))
        self.technological_set = set(self.bonus_extra.get("technological_set", []))

    # ---------- helpers ----------
    def _has_math_5(self, bagrut: BagrutRecord) -> bool:
        s = bagrut.find("Mathematics")
        return s is not None and s.units >= 5

    def _sci_tech_5u_counts(self, bagrut: BagrutRecord) -> Tuple[int, int]:
        sci = 0
        tech = 0
        for sg in bagrut.subjects:
            if sg.units >= 5 and sg.score >= self.min_score_for_bonus:
                if sg.name in self.scientific_set:
                    sci += 1
                if sg.name in self.technological_set:
                    tech += 1
        return sci, tech

    def _effective_weight(self, sg: SubjectGrade) -> float:
        if sg.name in self.double_weight_subjects:
            return float(sg.units) * 2.0
        return float(sg.units)

    def _base_bonus_per_subject(self, sg: SubjectGrade) -> float:
        if sg.score < self.min_score_for_bonus:
            return 0.0
        if sg.units >= 5:
            return self.base_bonus_5u
        if sg.units == 4:
            return self.base_bonus_4u
        return 0.0

    def _extra_bonus_5u_per_subject(self, sg: SubjectGrade, has_math_5: bool,
                                    has_two_sci_or_sci_plus_tech_5: bool) -> float:
        if sg.score < self.min_score_for_bonus or sg.units < 5:
            return 0.0
        if sg.name == "Mathematics":
            return self.extra_math_5u
        if sg.name in self.scientific_set or sg.name in self.technological_set:
            if has_math_5 and has_two_sci_or_sci_plus_tech_5:
                # when the aggregate condition holds, bump to 30
                return 30.0
            if sg.name in self.scientific_set:
                return self.extra_scientific_5u
            return self.extra_technological_5u
        return 0.0

    def _effective_score(self, sg: SubjectGrade, has_math_5: bool,
                         has_two_sci_or_sci_plus_tech_5: bool) -> float:
        # bonuses are per subject and added to that subject's score
        base = sg.score
        bonus = self._base_bonus_per_subject(sg)
        bonus += self._extra_bonus_5u_per_subject(sg, has_math_5, has_two_sci_or_sci_plus_tech_5)
        return base + bonus  # D will be capped globally

    def _allow_drop_jewish_philosophy(self, bagrut: BagrutRecord) -> bool:
        cond = self.allow_drop
        if not cond:
            return False
        if cond.get("subject") != "Literature":
            return False
        lit = bagrut.find("Literature")
        if lit is None:
            return False
        return lit.units >= int(cond.get("min_units", 2))

    def _collect_mandatory(self, bagrut: BagrutRecord) -> List[SubjectGrade]:
        # take names from subjects_catalog.mandatory (JSON)
        mandatory_names = [m["name"] for m in self.subjects_catalog.get("mandatory", [])]
        included: List[SubjectGrade] = []
        for name in mandatory_names:
            sg = bagrut.find(name)
            if sg is not None:
                included.append(sg)
        result: List[SubjectGrade] = []
        for sg in included:
            if sg.name == "Jewish Philosophy":
                if self._allow_drop_jewish_philosophy(bagrut):
                    continue
            result.append(sg)
        return result

    # ---------- main ----------
    def compute_D_with_breakdown(self, bagrut: BagrutRecord) -> Tuple[float, List[str]]:
        notes: List[str] = []
        mandatory = self._collect_mandatory(bagrut)

        has_math_5 = self._has_math_5(bagrut)
        sci_count, tech_count = self._sci_tech_5u_counts(bagrut)
        has_two_sci_or_sci_plus_tech_5 = (sci_count >= 2) or (sci_count >= 1 and tech_count >= 1)

        total_w = 0.0
        total_ws = 0.0

        # add mandatory
        for sg in mandatory:
            w = self._effective_weight(sg)
            s_eff = self._effective_score(sg, has_math_5, has_two_sci_or_sci_plus_tech_5)
            total_w += w
            total_ws += w * s_eff
            notes.append(f"MAND {sg.name}: units={sg.units}, effScore={s_eff:.2f}, weight={w}")

        # build elective pool (everything not counted as mandatory)
        mandatory_names = set(x.name for x in mandatory)
        pool: List[SubjectGrade] = []
        for sg in bagrut.subjects:
            if sg.name not in mandatory_names:
                pool.append(sg)

        # sort by effective score desc, tie-break by weight
        def sort_key(x: SubjectGrade):
            return (self._effective_score(x, has_math_5, has_two_sci_or_sci_plus_tech_5),
                    self._effective_weight(x))

        pool.sort(key=sort_key, reverse=True)

        # greedily add electives if they improve the average; stop once total_w >= min_total_units
        added = 0
        idx = 0
        while idx < len(pool):
            current_avg = 0.0 if total_w == 0.0 else (total_ws / total_w)
            cand = pool[idx]
            cand_w = self._effective_weight(cand)
            cand_s = self._effective_score(cand, has_math_5, has_two_sci_or_sci_plus_tech_5)
            new_avg = (total_ws + cand_w * cand_s) / (total_w + cand_w)
            if new_avg > current_avg:
                total_ws += cand_w * cand_s
                total_w += cand_w
                added += 1
                notes.append(f"ADD ELEC {cand.name}: effScore={cand_s:.2f}, weight={cand_w} -> avg {current_avg:.2f}→{new_avg:.2f}")
                if total_w >= float(self.min_total_units):
                    break
            idx += 1

        # final D + cap
        D = 0.0 if total_w == 0.0 else (total_ws / total_w)
        if D > self.max_D:
            notes.append(f"D capped {D:.2f}→{self.max_D:.2f}")
            D = self.max_D

        return D, notes
