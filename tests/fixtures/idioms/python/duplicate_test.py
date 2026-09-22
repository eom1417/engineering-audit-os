"""Same control-flow copied to many tests — true positive finding, should be reported."""
def test_path_a():
    validate("a")
    save("a")
    notify("a")

def test_path_b():
    validate("b")
    save("b")
    notify("b")

def test_path_c():
    validate("c")
    save("c")
    notify("c")
