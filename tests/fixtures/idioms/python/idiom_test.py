"""Idiomatic Python test patterns. Should NOT be reported as sequence clusters."""
def test_one_thing():
    assertEqual(1, 1)
    assertTrue(True)
    assertNotEqual(1, 2)

def test_another():
    assertEqual(2, 2)
    assertFalse(False)
    assertEqual(3, 3)

def test_third():
    assertEqual(4, 4)
    assertNotEqual(5, 6)
    assertTrue(7 == 7)
