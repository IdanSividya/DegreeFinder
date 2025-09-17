# backend/app.py
import os
import webbrowser
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import uvicorn

from backend.core.models import SubjectGrade, BagrutRecord, PsychometricScore, Applicant
from backend.core.engine import EligibilityEngine
from backend.core.repositories import JsonProgramRepository
from backend.core.rule_factory import RuleFactory
from backend.institutions.technion.loaders import load_subjects, load_policy, load_programs
from backend.institutions.technion.policy import TechnionPolicy

# נתיבים יחסיים לשורש הפרויקט
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))          # .../backend/..
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")               # .../frontend

def data_root_for(institution: str) -> str:
    if institution == "technion":
        return os.path.join(PROJECT_ROOT, "data", "technion")
    raise HTTPException(status_code=400, detail=f"Unsupported institution: {institution}")

app = FastAPI(title="Admissions Calculator")

# CORS לשימוש מקומי/דפדפן
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# הגשת ה-Frontend תחת /ui + הפניה מהשורש
app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")

@app.get("/")
def root_redirect():
    return RedirectResponse(url="/ui")

# --------- מודלי קלט ל־/compute ---------
class SubjectInput(BaseModel):
    name: str
    units: int
    score: float

class ComputeRequest(BaseModel):
    institutions: List[str]              # עכשיו אפשר כמה מוסדות
    psychometric_total: int
    subjects: List[SubjectInput]
    program_ids: Optional[List[str]] = None  # סינון אופציונלי של תארים (לפי ID)

# --------- API ---------
@app.get("/institutions")
def institutions() -> List[str]:
    # כרגע רק טכניון; המבנה כבר תומך בתוספות
    return ["technion"]

@app.get("/subjects")
def subjects(institution: Optional[str] = Query(None)) -> Dict[str, Any]:
    """
    מחזיר קטלוג מקצועות (חובה/בחירה).
    אם institution לא סופק – נחזיר כרגע את קטלוג הטכניון כברירת מחדל (כדי לאפשר הזנת ציונים מראש).
    """
    inst = institution or "technion"
    root = data_root_for(inst)
    return load_subjects(root)

@app.get("/programs")
def programs(institution: str) -> List[Dict[str, Any]]:
    """
    רשימת מסלולים (תארים) למוסד שנבחר – לשימוש ב-UI לבחירת תארים.
    """
    root = data_root_for(institution)
    progs = load_programs(root)
    out: List[Dict[str, Any]] = []
    for p in progs:
        out.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "faculty": p.get("faculty", ""),
            "institution": institution
        })
    return out

@app.post("/compute")
def compute(req: ComputeRequest) -> List[Dict[str, Any]]:
    if not req.institutions:
        raise HTTPException(status_code=400, detail="No institutions provided")

    # בניית מועמד מהקלט (ציוני בגרות+פסיכומטרי מוזנים פעם אחת)
    bagrut = BagrutRecord(
        subjects=[SubjectGrade(s.name, s.units, s.score) for s in req.subjects]
    )
    psychometric = PsychometricScore(total=req.psychometric_total)
    applicant = Applicant(bagrut=bagrut, psychometric=psychometric)

    # הערכה לכל מוסד נבחר; איחוד התוצאות לרשימה אחת
    aggregated: List[Dict[str, Any]] = []

    for inst in req.institutions:
        inst = inst.strip().lower()
        if inst != "technion":
            # כאן נוסיף תמיכה למוסדות נוספים בעתיד
            raise HTTPException(status_code=400, detail=f"Unsupported institution: {inst}")

        root = data_root_for(inst)
        policy_config = load_policy(root)
        subjects_catalog = load_subjects(root)
        programs_data = load_programs(root)

        policy = TechnionPolicy(policy_config, subjects_catalog)
        factory = RuleFactory(institution="technion", technion_policy=policy)
        repo = JsonProgramRepository(programs_data, factory)
        engine = EligibilityEngine(repo=repo, policy=policy)
        results = engine.evaluate_applicant(applicant)

        # אם נבחר סינון תארים – נשאיר רק את ה-IDs שסומנו
        selected_ids = set(req.program_ids or [])
        for r in results:
            if selected_ids and r.program.id not in selected_ids:
                continue
            item: Dict[str, Any] = {
                "institution": inst,
                "program_id": r.program.id,
                "program_name": r.program.name,
                "passed": r.passed,
                "explanations": r.explanations
            }
            if "D" in r.details:
                item["D"] = r.details["D"]
            if "P" in r.details:
                item["P"] = r.details["P"]
            if "S" in r.details:
                item["S"] = r.details["S"]
            if "threshold" in r.details:
                item["threshold"] = r.details["threshold"]
            aggregated.append(item)

    return aggregated

# --------- הפעלה מקומית ---------
if __name__ == "__main__":
    port = 8000
    url = f"http://localhost:{port}/ui"
    try:
        webbrowser.open(url)
    except Exception:
        pass
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=True)
