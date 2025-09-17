# backend/institutions/huji/policy.py
from typing import Dict, Any, Tuple, List
from backend.core.models import BagrutRecord, SubjectGrade

class HujiPolicy:
    """
    Hebrew University – exact spec:
    - Always include: English, Mathematics, History, Civics, and one language:
        Hebrew Language (Expression) for Hebrew-sector OR Arabic Language and Literature for Arab-sector (whichever exists in input).
    - Other mandatory (Literature, Bible, Jewish Philosophy) are OPTIONAL: include only if they improve the average and sum units stays ≥ 20.
    - Bonuses added PER SUBJECT before weighting:
        * English: +15(4u), +25(5u)
        * Mathematics: +15(4u), +35(5u)
        * Core 25-group (e.g., Physics/Chemistry/Biology/Computer Science/Arabic/History/Civics/Literature/Bible/Jewish Philosophy...):
              +15(4u), +25(5u)
        * Other-list: +10(4u), +20(5u)
        * Bonuses require units≥4 and score≥60
    - Optimal average: choose subset (with the always-included set) to maximize weighted mean s_eff over units,
      under the constraint sum_units ≥ 20. Add full subjects only (no partial units). Algorithm:
        1) Start with always-included; if units < 20, add highest s_eff electives until reaching ≥ 20.
        2) After reaching ≥ 20, add an elective only if it increases the current average.
    - Output D = weighted average on 0–100+ scale (can be >100).
    - Sechem 50/50:
        psychometric_std = a_p * P + b_p
        bagrut_tens     = D / 10
        bagrut_std      = a_b * bagrut_tens - b_b   (note the minus as per user spec)
        sechem          = ((0.5*bagrut_std + 0.5*psychometric_std) * alpha) - beta
        Round to 3 decimals.
      Constants provided via policy.json.
    """
    def __init__(self, policy_cfg: Dict[str, Any], subjects_catalog: Dict[str, Any]):
        self.cfg = policy_cfg
        self.subjects_catalog = subjects_catalog

        self.min_units = int(policy_cfg.get("min_total_units", 20))
        self.groups = policy_cfg.get("bonus_groups", {})
        self.mandatory_always = set(policy_cfg.get("mandatory_always", []))
        self.language_candidates = policy_cfg.get("language_mandatory_candidates", [])

        # sechem constants
        self.a_p = float(policy_cfg["psychometric_std"]["a"])
        self.b_p = float(policy_cfg["psychometric_std"]["b"])
        self.a_b = float(policy_cfg["bagrut_std"]["a"])
        self.b_b = float(policy_cfg["bagrut_std"]["b"])
        self.alpha = float(policy_cfg["sechem"]["alpha"])
        self.beta = float(policy_cfg["sechem"]["beta"])

    # ---------- bonus helpers ----------
    def _bonus_for(self, s: SubjectGrade) -> float:
        if s.units < 4:
            return 0.0
        if s.score < 60:
            return 0.0

        name = s.name
        u = s.units

        # math
        if name == "Mathematics":
            if u >= 5:
                return 35.0
            if u == 4:
                return 15.0

        # english
        if name == "English":
            if u >= 5:
                return 25.0
            if u == 4:
                return 15.0

        # core_25 group: +25 (5u) / +15 (4u)
        core25 = set(self.groups.get("core_25", []))
        if name in core25:
            if u >= 5:
                return 25.0
            if u == 4:
                return 15.0

        # other_20 group: +20 (5u) / +10 (4u)
        other20 = set(self.groups.get("other_20", []))
        if name in other20:
            if u >= 5:
                return 20.0
            if u == 4:
                return 10.0

        return 0.0

    def _eff_score(self, s: SubjectGrade) -> float:
        return s.score + self._bonus_for(s)

    # ---------- selection helpers ----------
    def _choose_language_mandatory(self, bagrut: BagrutRecord) -> SubjectGrade:
        # Prefer the one actually present; if both present, prefer Hebrew by default
        heb = bagrut.find("Hebrew Language (Expression)")
        arb = bagrut.find("Arabic Language and Literature")
        if heb is not None:
            return heb
        if arb is not None:
            return arb
        # if neither exists, we do not fail hard; just omit (the UI validation can warn)
        return None  # type: ignore

    def compute_D_with_breakdown(self, bagrut: BagrutRecord) -> Tuple[float, List[str]]:
        notes: List[str] = []

        # Always-included core: English, Mathematics, History, Civics, and language candidate
        always_names = set(self.mandatory_always)
        lang = self._choose_language_mandatory(bagrut)
        if lang is not None:
            always_names.add(lang.name)

        included: List[SubjectGrade] = []
        for name in always_names:
            s = bagrut.find(name)
            if s is not None:
                included.append(s)

        # prepare pool = all others (including Literature/Bible/Jewish Philosophy etc.)
        included_names = set(x.name for x in included)
        pool: List[SubjectGrade] = []
        for s in bagrut.subjects:
            if s.name not in included_names:
                pool.append(s)

        # base sum
        sum_w = 0.0
        sum_ws = 0.0
        for s in included:
            w = float(s.units)
            es = self._eff_score(s)
            sum_w += w
            sum_ws += w * es
            notes.append(f"MAND {s.name}: units={s.units}, eff={es:.2f}")

        # sort pool by eff score desc, then units desc
        pool.sort(key=lambda x: (self._eff_score(x), x.units), reverse=True)

        # Step 1: reach at least min units (even if hurts average)
        idx = 0
        while sum_w < float(self.min_units) and idx < len(pool):
            cand = pool[idx]
            w = float(cand.units)
            es = self._eff_score(cand)
            sum_ws += w * es
            sum_w += w
            notes.append(f"ADD to reach {self.min_units}: {cand.name} eff={es:.2f}, w={w}")
            idx += 1

        # Step 2: only add if improves current average
        while idx < len(pool):
            cand = pool[idx]
            w = float(cand.units)
            es = self._eff_score(cand)
            cur_avg = 0.0 if sum_w == 0.0 else (sum_ws / sum_w)
            new_avg = (sum_ws + w * es) / (sum_w + w)
            if new_avg > cur_avg:
                sum_ws += w * es
                sum_w += w
                notes.append(f"IMPROVE {cand.name}: {cur_avg:.2f}→{new_avg:.2f}")
            idx += 1

        D = 0.0 if sum_w == 0.0 else (sum_ws / sum_w)
        notes.append(f"D (0–100+ scale) = {D:.6f}, units={sum_w:.2f}")
        return D, notes

    def compute_sechem(self, d_raw: float, p_total: int) -> float:
        # Apply exact HUJI formulas
        psych_std = self.a_p * float(p_total) + self.b_p
        bagrut_tens = d_raw / 10.0
        bagrut_std = self.a_b * bagrut_tens - self.b_b
        s = ((0.5 * bagrut_std + 0.5 * psych_std) * self.alpha) - self.beta
        # Round to 3 decimals as requested
        return round(s, 3)
