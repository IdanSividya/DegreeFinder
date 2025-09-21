import pytest
from backend.core.engine import EligibilityEngine
from backend.core.models import Applicant, BagrutRecord, PsychometricScore

def test_engine_basic():
    applicant = Applicant(
        bagrut=BagrutRecord(subjects=[]),
        psychometric=PsychometricScore(score=700)
    )
    engine = EligibilityEngine()
    # Replace with actual logic and assertions
    assert hasattr(engine, 'check_eligibility')

