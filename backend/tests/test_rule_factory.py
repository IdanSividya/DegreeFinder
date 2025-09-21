from backend.core.rule_factory import RuleFactory

def test_rule_factory():
    factory = RuleFactory()
    assert hasattr(factory, 'create_rule')

