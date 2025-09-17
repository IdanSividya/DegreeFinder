from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple
from backend.core.models import BagrutRecord, SubjectGrade

@dataclass
class BguComputeResult:
    D: float                              # ממוצע בגרויות אחרי בונוסים (0–120)
    included_subjects: List[Dict[str, float]]  # פירוט המקצועות שנכללו
    total_units: int

class BguPolicy:
    """
    מדיניות בן-גוריון – 'ממוצע בגרות אופטימלי' + סכם 50/50

    כללים:
    1) תמיד נכללים: אנגלית, מתמטיקה, היסטוריה, אזרחות, הבעה בעברית.
    2) משלימים לבערך ≥20 יח״ל בבחירה אופטימלית: מוסיפים רק מקצועות שמשפרים את הממוצע.
       מקצוע שנכנס נספר במלוא היח״ל שלו, גם אם עוברים את 20.
    3) בונוסים ניתנים רק לציון מקורי ≥60 ולמקצוע בהיקף 4–5 יח״ל.
       כלליים: 4 יח״ל +10, 5 יח״ל +20.
       החרגות:
         • מתמטיקה: 5 יחל +35, 4 יחל +20
         • אנגלית: 5 יחל +25, 4 יחל +15
         • 'מוגבר +25' ב-5 יחל: פיזיקה/כימיה/ביולוגיה/ספרות/תנ״ך/היסטוריה/מדעי המחשב
         • ערבית (מסלול יהודי): 5 יחל +20 (לא +25)
       מקצוע בין-תחומי: ללא בונוס.
    4) תקרת ממוצע: 120.
    5) סכם 50/50:
         B = 650 + 10 * (D - 100)
         S = (B + P) / 2
    """

    def __init__(self) -> None:
        self.mandatory_names = set([
            "english",
            "mathematics",
            "history",
            "civics",
            "hebrew_expression",
        ])

        self.plus25_five_units = set([
            "physics",
            "chemistry",
            "biology",
            "literature",
            "bible",
            "history",
            "computer_science",
        ])

        self.no_bonus_names = set([
            "interdisciplinary",
            "multi_disciplinary",
            "interdisciplinary_studies",
        ])

    # ---------- API שהחוקים מצפים לו ----------
    # מחזיר D ופירוט; משמש ע״י מחלקת הסף להצגת D וכד'
    def compute_D_with_breakdown(self, bagrut: BagrutRecord) -> Dict[str, float]:
        result = self._compute_optimal_average(bagrut)
        return {"D": result.D}

    # חישוב S (וסיוע להצגת B אם צריך)
    def compute_S_50_50(self, D: float, psychometric_total: float) -> Tuple[float, float]:
        bagrut_component = 650.0 + 10.0 * (D - 100.0)
        sakem = (bagrut_component + float(psychometric_total)) / 2.0
        return sakem, bagrut_component

    # ---------- לוגיקה פנימית ----------
    def _compute_optimal_average(self, bagrut: BagrutRecord) -> BguComputeResult:
        # 1) מפרידים חובה ובחירה
        mandatory_subjects: List[SubjectGrade] = []
        elective_subjects: List[SubjectGrade] = []

        for sg in bagrut.subjects:
            normalized = sg.name.lower()
            if normalized in self.mandatory_names:
                mandatory_subjects.append(sg)
            else:
                elective_subjects.append(sg)

        # 2) מתחילים עם החובה
        included: List[SubjectGrade] = list(mandatory_subjects)
        current_sum, current_units = self._sum_and_units(included)

        # 3) משלימים ל-≥20 יח״ל בבחירה גרידית לפי שיפור ממוצע
        while current_units < 20:
            best_subject = None
            best_new_avg = None

            for cand in elective_subjects:
                if cand in included:
                    continue
                trial_sum, trial_units = self._sum_and_units(included + [cand])
                trial_avg = self._average_from_sum(trial_sum, trial_units)
                if best_subject is None:
                    best_subject = cand
                    best_new_avg = trial_avg
                else:
                    if trial_avg > best_new_avg:
                        best_subject = cand
                        best_new_avg = trial_avg

            if best_subject is None:
                break  # אין מה להוסיף

            included.append(best_subject)
            current_sum, current_units = self._sum_and_units(included)

            if current_units >= 20:
                break

        # 4) מוסיפים מקצועות נוספים רק אם משפרים ממוצע
        improved = True
        while improved:
            improved = False
            base_sum, base_units = self._sum_and_units(included)
            base_avg = self._average_from_sum(base_sum, base_units)

            best_gain = 0.0
            best_subject_to_add = None

            for cand in elective_subjects:
                if cand in included:
                    continue
                trial_sum, trial_units = self._sum_and_units(included + [cand])
                trial_avg = self._average_from_sum(trial_sum, trial_units)
                gain = trial_avg - base_avg
                if gain > best_gain:
                    best_gain = gain
                    best_subject_to_add = cand

            if best_subject_to_add is not None and best_gain > 0.0:
                included.append(best_subject_to_add)
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

        return BguComputeResult(D=D, included_subjects=breakdown, total_units=final_units)

    def _sum_and_units(self, subset: List[SubjectGrade]) -> Tuple[float, int]:
        weighted_sum = 0.0
        total_units = 0
        for sg in subset:
            bonus = self._bonus_for(sg)
            score_after_bonus = sg.score + bonus
            weighted_sum += score_after_bonus * sg.units
            total_units += sg.units
        return weighted_sum, total_units

    def _average_from_sum(self, weighted_sum: float, total_units: int) -> float:
        if total_units == 0:
            return 0.0
        return weighted_sum / float(total_units)

    def _bonus_for(self, sg: SubjectGrade) -> float:
        name = sg.name.lower()
        units = sg.units
        raw = sg.score

        if raw < 60:
            return 0.0
        if units < 4:
            return 0.0
        if name in self.no_bonus_names:
            return 0.0

        # מתמטיקה
        if name == "mathematics" or name == "math":
            if units == 5:
                return 35.0
            if units == 4:
                return 20.0
            return 0.0

        # אנגלית
        if name == "english":
            if units == 5:
                return 25.0
            if units == 4:
                return 15.0
            return 0.0

        # ערבית – מסלול יהודי: 5 יח״ל +20, 4 יח״ל +10
        if name == "arabic":
            if units == 5:
                return 20.0
            if units == 4:
                return 10.0
            return 0.0

        # מוגבר +25 ב-5 יח״ל לקבוצת המקצועות שהוגדרה
        if name in self.plus25_five_units:
            if units == 5:
                return 25.0
            if units == 4:
                return 10.0
            return 0.0

        # כלליים
        if units == 5:
            return 20.0
        if units == 4:
            return 10.0
        return 0.0
