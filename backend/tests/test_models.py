from backend.core.models import SubjectGrade, BagrutRecord, PsychometricScore, Applicant

def test_subject_grade():
    sg = SubjectGrade(name='Math', units=5, grade=95)
    assert sg.name == 'Math'
    assert sg.units == 5
    assert sg.grade == 95

def test_bagrut_record():
    br = BagrutRecord(subjects=[])
    assert isinstance(br.subjects, list)

def test_psychometric_score():
    ps = PsychometricScore(score=700)
    assert ps.score == 700

def test_applicant():
    a = Applicant(bagrut=BagrutRecord(subjects=[]), psychometric=PsychometricScore(score=700))
    assert isinstance(a.bagrut, BagrutRecord)
    assert isinstance(a.psychometric, PsychometricScore)

