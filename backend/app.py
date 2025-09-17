import os
import webbrowser
from typing import List, Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.core.models import SubjectGrade, BagrutRecord, PsychometricScore, Applicant
from backend.core.engine import EligibilityEngine
from backend.core.repositories import JsonProgramRepository
from backend.core.rule_factory import RuleFactory

# ---------- Technion ----------
from backend.institutions.technion.loaders import (
    load_subjects as tech_load_subjects,
    load_policy as tech_load_policy,
    load_programs as tech_load_programs,
)
from backend.institutions.technion.policy import TechnionPolicy

# ---------- Hebrew University ----------
from backend.institutions.huji.loaders import (
    load_subjects as huji_load_subjects,
    load_policy as huji_load_policy,
    load_programs as huji_load_programs,
)
from backend.institutions.huji.policy import HujiPolicy

# ---------- Ben-Gurion University ----------
from backend.institutions.bgu.loaders import (
    load_subjects as bgu_load_subjects,
    load_policy as bgu_load_policy,
    load_programs as bgu_load_programs,
)
from backend.institutions.bgu.policy import BguPolicy


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")


def data_root_for(institution: str) -> str:
    inst = (institution or "").lower().strip()
    if inst == "technion":
        return os.path.join(PROJECT_ROOT, "data", "technion")
    if inst == "huji":
        return os.path.join(PROJECT_ROOT, "data", "huji")
    if inst == "bgu":
        return os.path.join(PROJECT_ROOT, "data", "bgu")
    raise HTTPException(status_code=400, detail=f"Unsupported institution: {institution}")


app = FastAPI(title="Admissions Calculator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the static UI
app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/ui")


# --------- Request models ----------
class SubjectInput(BaseModel):
    name: str
    units: int
    score: float


class ComputeRequest(BaseModel):
    institutions: List[str]
    psychometric_total: int
    subjects: List[SubjectInput]
    program_ids: Optional[List[str]] = None


# --------- Endpoints ----------
@app.get("/institutions")
def institutions() -> List[str]:
    # Order here is only for UI convenience
    return ["technion", "huji", "bgu"]


@app.get("/subjects")
def subjects(institution: Optional[str] = Query(None)) -> Dict[str, Any]:
    inst = (institution or "technion").lower().strip()
    root = data_root_for(inst)
    if inst == "technion":
        return tech_load_subjects(root)
    if inst == "huji":
        return huji_load_subjects(root)
    if inst == "bgu":
        return bgu_load_subjects(root)
    raise HTTPException(status_code=400, detail="Unsupported institution")


@app.get("/programs")
def programs(institution: str) -> List[Dict[str, Any]]:
    inst = (institution or "").lower().strip()
    root = data_root_for(inst)

    if inst == "technion":
        progs = tech_load_programs(root)
    elif inst == "huji":
        progs = huji_load_programs(root)
    elif inst == "bgu":
        progs = bgu_load_programs(root)
    else:
        raise HTTPException(status_code=400, detail="Unsupported institution")

    # Return only the fields the frontend needs. No "category" here.
    out: List[Dict[str, Any]] = []
    for p in progs:
        out.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "faculty": p.get("faculty", ""),
            "institution": inst
        })
    return out


@app.post("/compute")
def compute(req: ComputeRequest):
    try:
        if not req.institutions:
            raise HTTPException(status_code=400, detail="No institutions provided")

        # Build applicant
        bagrut = BagrutRecord(
            subjects=[SubjectGrade(s.name, s.units, s.score) for s in req.subjects]
        )
        psychometric = PsychometricScore(total=req.psychometric_total)
        applicant = Applicant(bagrut=bagrut, psychometric=psychometric)

        aggregated: List[Dict[str, Any]] = []
        selected_ids = set(req.program_ids) if req.program_ids is not None else set()

        for inst in req.institutions:
            inst_norm = (inst or "").lower().strip()
            root = data_root_for(inst_norm)

            # Load institution-specific resources and policy
            if inst_norm == "technion":
                policy_cfg = tech_load_policy(root)
                catalog = tech_load_subjects(root)
                programs = tech_load_programs(root)
                policy = TechnionPolicy(policy_cfg, catalog)
                factory = RuleFactory(institution="technion", technion_policy=policy)

            elif inst_norm == "huji":
                policy_cfg = huji_load_policy(root)
                catalog = huji_load_subjects(root)
                programs = huji_load_programs(root)
                policy = HujiPolicy(policy_cfg, catalog)
                factory = RuleFactory(institution="huji", huji_policy=policy)

            elif inst_norm == "bgu":
                policy_cfg = bgu_load_policy(root)
                catalog = bgu_load_subjects(root)
                programs = bgu_load_programs(root)
                policy = BguPolicy(policy_cfg, catalog)
                factory = RuleFactory(institution="bgu", bgu_policy=policy)

            else:
                raise HTTPException(status_code=400, detail=f"Unsupported institution: {inst_norm}")

            repo = JsonProgramRepository(programs, factory)
            engine = EligibilityEngine(repo=repo, policy=policy)
            results = engine.evaluate_applicant(applicant)

            for r in results:
                if selected_ids and r.program.id not in selected_ids:
                    continue
                item: Dict[str, Any] = {
                    "institution": inst_norm,
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

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Compute failed", "details": str(e)}
        )


if __name__ == "__main__":
    port = 8000
    url = f"http://localhost:{port}/ui"
    try:
        webbrowser.open(url)
    except Exception:
        pass
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=True)
