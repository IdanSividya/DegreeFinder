from backend.core.repositories import JsonProgramRepository

def test_repository_init():
    repo = JsonProgramRepository(json_path='dummy.json')
    assert hasattr(repo, 'json_path')

