# backend/institutions/technion/policy.py
from typing import Dict, Any, Tuple, List
from backend.core.models import BagrutRecord, SubjectGrade

class TechnionPolicy:
    """
    Technion D calculation (fixed to match the official calculator logic):
    - Mandatory subjects are always included (with the option to drop 'Jewish Philosophy' if Literature >= 2u).
    - Mathematics has double weight (via 'double_weight_subjects' in policy.json).
    - Bonuses for 5 units are CATEGORY-BASED and DO NOT STACK:
        * Mathematics 5u: +30 only (no base 5u bonus on top).
        * Scientific/Technological 5u: +25, or +30 if the aggregate condition holds
          (Math 5u AND (two scientific 5u OR one scientific 5u + one technological 5u)).
        * Other 5u (e.g., languages): base 5u bonus from policy.json (recommend 25).
      For 4u: base bonus applies as usual (e.g., +10) if score >= min_score_for_bonus.
    - Electives are added greedily if and only if they IMPROVE the weighted average;
      we DO NOT stop just because we reached 20 units — we continue to add improving electives.
    - Cap D at max_D (e.g., 119).
    """

    def __init__(self, policy_cfg: Dict[str, Any], subjects_catalog: Dict[str, Any]):
        self.cfg = policy_cfg
        self.subjects_catalog = subjects_catalog

        # weighting
        self.double_weight_subjects = set(policy_cfg.get("double_weight_subjects", []))
        self.min_total_units = int(policy_cfg.get("min_total_units", 20))
        self.max_D = float(policy_cfg.get("max_D", 119.0))

        # optional drop of 'Jewish Philosophy' if Literature>=2
        self.allow_drop = policy_cfg.get("allow_drop_jewish_philosophy_if", None)

        # base bonuses
        self.bonus_base = policy_cfg.get("bonus_base", {})
        self.min_score_for_bonus = float(self.bonus_base.get("min_score", 60))
        self.base_bonus_4u = float(self.bonus_base.get("4u", 10))
        # IMPORTANT: set '5u' to 25 in policy.json to align with the official calculator
        self.base_bonus_5u = float(self.bonus_base.get("5u", 25))

        # extra (category) bonuses for 5u
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
        # double weight for Mathematics (and any subject listed in policy.json)
        if sg.name in self.double_weight_subjects:
            return float(sg.units) * 2.0
        return float(sg.units)

    # ---- NEW: category-based 5u bonus (no stacking) ----
    def _category_bonus_5u(self, sg: SubjectGrade, has_math_5: bool,
                           has_two_sci_or_sci_plus_tech_5: bool) -> float:
        if sg.units < 5 or sg.score < self.min_score_for_bonus:
            return 0.0
        # 1) Mathematics – 30 only
        if sg.name == "Mathematics":
            return self.extra_math_5u  # 30

        # 2) Scientific/Technological – 25, or 30 if aggregate condition holds
        if sg.name in self.scientific_set or sg.name in self.technological_set:
            if has_math_5 and has_two_sci_or_sci_plus_tech_5:
                return self.extra_aggregate_bump  # 30
            # per-category default
            return self.extra_scientific_5u if sg.name in self.scientific_set else self.extra_technological_5u  # 25

        # 3) Other 5u (languages, humanities 5u, etc.) – base 5u bonus from policy
        return self.base_bonus_5u  # recommend 25 in policy.json

    def _effective_score(self, sg: SubjectGrade, has_math_5: bool,
                         has_two_sci_or_sci_plus_tech_5: bool) -> float:
        base = sg.score
        # 4u: base bonus (e.g., +10) if eligible
        if sg.units == 4 and sg.score >= self.min_score_for_bonus:
            return base + self.base_bonus_4u

        # 5u: category-based bonus (NO stacking of base+extra)
        if sg.units >= 5 and sg.score >= self.min_score_for_bonus:
            return base + self._category_bonus_5u(sg, has_math_5, has_two_sci_or_sci_plus_tech_5)

        # <4u or below min score: no bonus
        return base

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

        # 1) add mandatory
        for sg in mandatory:
            w = self._effective_weight(sg)
            s_eff = self._effective_score(sg, has_math_5, has_two_sci_or_sci_plus_tech_5)
            total_w += w
            total_ws += w * s_eff
            notes.append(f"MAND {sg.name}: units={sg.units}, effScore={s_eff:.2f}, weight={w}")

        # 2) elective pool = subjects not counted as mandatory
        mandatory_names = set(x.name for x in mandatory)
        pool: List[SubjectGrade] = [sg for sg in bagrut.subjects if sg.name not in mandatory_names]

        # sort by effective score (desc), then by weight
        def sort_key(x: SubjectGrade):
            return (self._effective_score(x, has_math_5, has_two_sci_or_sci_plus_tech_5),
                    self._effective_weight(x))
        pool.sort(key=sort_key, reverse=True)

        # 3) greedily add electives if they IMPROVE the average (no hard stop at 20)
        idx = 0
        while idx < len(pool):
            current_avg = 0.0 if total_w == 0.0 else (total_ws / total_w)
            cand = pool[idx]
            cand_w = self._effective_weight(cand)
            cand_s = self._effective_score(cand, has_math_5, has_two_sci_or_sci_plus_tech_5)
            new_avg = (total_ws + cand_w * cand_s) / (total_w + cand_w)
            if new_avg > current_avg:
                total_ws += cand_w * cand_s
                total_w  += cand_w
                notes.append(f"ADD ELEC {cand.name}: effScore={cand_s:.2f}, weight={cand_w} -> avg {current_avg:.2f}→{new_avg:.2f}")
                # NOTE: do NOT break at min_total_units; continue if it keeps improving
            idx += 1

        # 4) final D with cap
        D = 0.0 if total_w == 0.0 else (total_ws / total_w)
        if D > self.max_D:
            notes.append(f"D capped {D:.2f}→{self.max_D:.2f}")
            D = self.max_D

        return D, notes
