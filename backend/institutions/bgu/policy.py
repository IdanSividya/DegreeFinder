from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

from backend.core.models import BagrutRecord, SubjectGrade, Applicant


@dataclass
class BguComputeResult:
    D: float                                  # ממוצע בגרויות אחרי בונוסים (יכול לעלות מעל 100, תקרה 120)
    included_subjects: List[Dict[str, float]] # פירוט המקצועות שנכללו בחישוב
    total_units: int


class BguPolicy:
    """
    מדיניות בן-גוריון – 'ממוצע בגרות אופטימלי' + סכם 50/50.

    כללים תמציתית:
      • תמיד נכללים: אנגלית, מתמטיקה, היסטוריה, אזרחות, הבעה עברית.
      • משלימים ל־≥20 יח״ל בבחירה אופטימלית: מוסיפים רק מקצועות שמשפרים את הממוצע;
        מקצוע שנכנס נספר במלוא היח״ל שלו (גם אם עוברים את 20).
      • בונוסים (ציון ≥60 ובהיקף 4–5 יח״ל):
          מתמטיקה: 5→+35, 4→+20
          אנגלית:  5→+25, 4→+15
          קבוצת “מוגבר +25” ב־5 יח״ל: פיזיקה/כימיה/ביולוגיה/ספרות/תנ״ך/היסטוריה/מדעי המחשב
          ערבית (בזרם היהודי): 5→+20, 4→+10
          מקצועות בין תחומיים: ללא בונוס
          כלליים: 5→+20, 4→+10
      • תקרת ממוצע: 120.
      • סכם: B = 650 + 10*(D - 100),  S = (B + P) / 2
    """

    # שמרתי חתימת אתחול תואמת לשאר המוסדות כדי למנוע TypeError מיותרים
    def __init__(self, config: Optional[Dict] = None, subjects_catalog: Optional[Dict] = None) -> None:
        self.mandatory_names = {
            "english",
            "mathematics",
            "history",
            "civics",
            "hebrew_expression",
        }
        self.plus25_five_units = {
            "physics",
            "chemistry",
            "biology",
            "literature",
            "bible",
            "history",
            "computer_science",
        }
        self.no_bonus_names = {
            "interdisciplinary",
            "multi_disciplinary",
            "interdisciplinary_studies",
        }

    # ---------- API שהמערכת מצפה לו ----------

    # כאן אני מחזיר בדיוק מה שה־engine שלך מצפה: (D, breakdown)
    def compute_D_with_breakdown(self, bagrut: BagrutRecord) -> Tuple[float, List[Dict[str, float]]]:
        res = self._compute_optimal_average(bagrut)
        return float(res.D), res.included_subjects

    # כלל הסף של BGU משתמש בזה (ראו BguSakemThresholdRule)
    # מחזיר (details_dict, explanations_list)
    def compute_sakem(self, applicant: Applicant) -> Tuple[Dict[str, float], List[str]]:
        D, breakdown = self.compute_D_with_breakdown(applicant.bagrut)
        P = float(applicant.psychometric.total)
        B = 650.0 + 10.0 * (D - 100.0)
        S = (B + P) / 2.0
        details = {"D": float(D), "B": float(B), "P": P, "S": float(S)}
        # שורת הסבר קצרה; אפשר להרחיב בעתיד לפי הצורך
        explanations = [f"BGU: D={D:.3f}, B={B:.1f}, P={P:.0f}, S={S:.3f}"]
        return details, explanations

    # ---------- לוגיקה פנימית ----------

    def _compute_optimal_average(self, bagrut: BagrutRecord) -> BguComputeResult:
        # 1) מפרידים חובה ובחירה
        mandatory_subjects: List[SubjectGrade] = []
        elective_subjects: List[SubjectGrade] = []

        for sg in bagrut.subjects:
            name = (sg.name or "").lower()
            if name in self.mandatory_names:
                mandatory_subjects.append(sg)
            else:
                elective_subjects.append(sg)

        # 2) נתחיל עם החובה
        included: List[SubjectGrade] = list(mandatory_subjects)
        current_sum, current_units = self._sum_and_units(included)

        # 3) משלימים ל־≥20 יח״ל בבחירה גרידית: בכל צעד בוחרים את ההוספה שמשפרת ממוצע הכי הרבה
        while current_units < 20 and elective_subjects:
            best_subj = None
            best_avg = None
            for cand in elective_subjects:
                if cand in included:
                    continue
                trial_sum, trial_units = self._sum_and_units(included + [cand])
                trial_avg = self._average_from_sum(trial_sum, trial_units)
                if best_subj is None or trial_avg > best_avg:
                    best_subj = cand
                    best_avg = trial_avg
            if best_subj is None:
                break
            included.append(best_subj)
            current_sum, current_units = self._sum_and_units(included)

        # 4) אפשר להוסיף מעבר ל־20 רק אם זה משפר ממוצע
        improved = True
        while improved:
            improved = False
            base_sum, base_units = self._sum_and_units(included)
            base_avg = self._average_from_sum(base_sum, base_units)

            best_gain = 0.0
            best_to_add = None
            for cand in elective_subjects:
                if cand in included:
                    continue
                trial_sum, trial_units = self._sum_and_units(included + [cand])
                trial_avg = self._average_from_sum(trial_sum, trial_units)
                gain = trial_avg - base_avg
                if gain > best_gain:
                    best_gain = gain
                    best_to_add = cand

            if best_to_add is not None and best_gain > 0.0:
                included.append(best_to_add)
                improved = True

        final_sum, final_units = self._sum_and_units(included)
        D = self._average_from_sum(final_sum, final_units)
        if D > 120.0:
            D = 120.0

        breakdown: List[Dict[str, float]] = []
        for sg in included:
            bonus = self._bonus_for(sg)
            score_after_bonus = sg.score + bonus
            contribution = score_after_bonus * sg.units
            breakdown.append({
                "name": sg.name,
                "units": float(sg.units),
                "score": float(sg.score),
                "bonus": float(bonus),
                "score_after_bonus": float(score_after_bonus),
                "contribution": float(contribution),
            })

        return BguComputeResult(D=float(D), included_subjects=breakdown, total_units=final_units)

    def _sum_and_units(self, subset: List[SubjectGrade]) -> Tuple[float, int]:
        weighted_sum = 0.0
        total_units = 0
        for sg in subset:
            bonus = self._bonus_for(sg)
            weighted_sum += (sg.score + bonus) * sg.units
            total_units += sg.units
        return weighted_sum, total_units

    def _average_from_sum(self, weighted_sum: float, total_units: int) -> float:
        return 0.0 if total_units == 0 else (weighted_sum / float(total_units))

    def _bonus_for(self, sg: SubjectGrade) -> float:
        name = (sg.name or "").lower()
        units = int(sg.units)
        raw = float(sg.score)

        if raw < 60 or units < 4:
            return 0.0
        if name in self.no_bonus_names:
            return 0.0

        # מתמטיקה
        if name in ("mathematics", "math"):
            return 35.0 if units == 5 else (20.0 if units == 4 else 0.0)

        # אנגלית
        if name == "english":
            return 25.0 if units == 5 else (15.0 if units == 4 else 0.0)

        # ערבית (בזרם היהודי)
        if name == "arabic":
            return 20.0 if units == 5 else (10.0 if units == 4 else 0.0)

        # קבוצת “מוגבר +25” ב־5 יח״ל
        if name in self.plus25_five_units:
            return 25.0 if units == 5 else (10.0 if units == 4 else 0.0)

        # כלליים
        return 20.0 if units == 5 else (10.0 if units == 4 else 0.0)
