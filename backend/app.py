from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import uvicorn
import webbrowser
import os

from backend.core.models import SubjectGrade, BagrutRecord, PsychometricScore, Applicant
from backend.core.engine import EligibilityEngine
from backend.core.repositories import JsonProgramRepository
from backend.core.rule_factory import RuleFactory
from backend.institutions.technion.loaders import load_subjects, load_policy, load_programs
from backend.institutions.technion.policy import TechnionPolicy

DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "technion")

app = FastAPI(title="Admissions Calculator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SubjectInput(BaseModel):
    name: str
    units: int
    score: float

class ComputeRequest(BaseModel):
    institution: str
    psychometric_total: int
    subjects: List[SubjectInput]

@app.get("/institutions")
def institutions() -> List[str]:
    return ["technion"]

@app.get("/subjects")
def subjects(institution: str) -> Dict[str, Any]:
    if institution != "technion":
        raise HTTPException(status_code=400, detail="Unsupported institution")
    subj = load_subjects(DATA_ROOT)
    return subj

@app.post("/compute")
def compute(req: ComputeRequest) -> List[Dict[str, Any]]:
    if req.institution != "technion":
        raise HTTPException(status_code=400, detail="Unsupported institution")

    # Load data and policy
    policy_config = load_policy(DATA_ROOT)
    subjects_catalog = load_subjects(DATA_ROOT)
    programs_data = load_programs(DATA_ROOT)

    # Build applicant
    bagrut = BagrutRecord(
        subjects=[SubjectGrade(s.name, s.units, s.score) for s in req.subjects]
    )
    psychometric = PsychometricScore(total=req.psychometric_total)
    applicant = Applicant(bagrut=bagrut, psychometric=psychometric)

    # Policy + rules
    policy = TechnionPolicy(policy_config, subjects_catalog)
    factory = RuleFactory(institution="technion", technion_policy=policy)
    repo = JsonProgramRepository(programs_data, factory)
    engine = EligibilityEngine(repo=repo, policy=policy)

    results = engine.evaluate_applicant(applicant)
    response = []
    for r in results:
        response.append({
            "program_id": r.program.id,
            "program_name": r.program.name,
            "passed": r.passed,
            "S": r.details.get("S"),
            "D": r.details.get("D"),
            "P": r.details.get("P"),
            "threshold": r.details.get("threshold"),
            "explanations": r.explanations
        })
    return response

if __name__ == "__main__":
    port = 8000
    url = f"http://localhost:{port}"
    webbrowser.open(url)
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=True)
