import sys
import threading
from mlx_mcp_server import LogCapturingStream, StderrTee, _guarded_stdout

def test_nested_callbacks():
    print("Testing nested callbacks...")
    tee = StderrTee(sys.stderr)
    sys.stderr = tee

    captured_outer = []
    captured_inner = []

    def outer_callback(data):
        captured_outer.append(data)

    def inner_callback(data):
        captured_inner.append(data)

    # 1. Register outer
    tee.set_callback(outer_callback)
    sys.stderr.write("Outer 1\n")

    # 2. Register inner (nested)
    tee.set_callback(inner_callback)
    sys.stderr.write("Inner 1\n")

    # 3. Pop inner
    tee.clear_callback()
    sys.stderr.write("Outer 2\n")

    # 4. Pop outer
    tee.clear_callback()
    sys.stderr.write("None\n")

    sys.stderr = tee.original_stderr

    assert "Outer 1\n" in captured_outer
    assert "Outer 2\n" in captured_outer
    assert "Inner 1\n" not in captured_outer

    assert "Inner 1\n" in captured_inner
    assert "Outer 1\n" not in captured_inner
    assert "Outer 2\n" not in captured_inner

    print("✓ Nested callbacks verified successfully!")

def test_stdout_redirection():
    print("Testing stdout redirection...")
    tee = StderrTee(sys.stderr)
    sys.stderr = tee

    captured = []
    tee.set_callback(lambda data: captured.append(data))

    # Guarded stdout write should bypass real stdout and go to sys.stderr on non-MCP threads
    sys.stdout.write("Hello from redirected stdout!\n")

    sys.stderr = tee.original_stderr

    assert "Hello from redirected stdout!\n" in captured
    print("✓ Stdout redirection teed successfully!")

if __name__ == "__main__":
    test_nested_callbacks()
    test_stdout_redirection()
    print("All nested and redirection tests passed!")
