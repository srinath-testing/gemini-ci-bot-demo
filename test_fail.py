# Intentional failing test to trigger CI failure
def test_always_fails():
    """This test always fails to demonstrate bot behavior on test failures"""
    assert 1 == 2, "This test is designed to fail"

def test_another_failure():
    """Another failing test"""
    result = 5 + 5
    assert result == 11, "Math is broken"