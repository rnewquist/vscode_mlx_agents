import sys
import threading
import time
from mlx_mcp_server import LogCapturingStream, StderrTee

def test_log_capturing_stream():
    print("Testing LogCapturingStream...")
    stream = LogCapturingStream()
    
    # 1. Simple writes
    stream.write("Hello\nWorld\n")
    assert stream.getvalue() == "Hello\nWorld\n", f"Expected 'Hello\\nWorld\\n', got {repr(stream.getvalue())}"
    
    # 2. Carriage return overwrite
    stream.write("Loading:  10%\r")
    stream.write("Loading:  20%\nDone\n")
    assert stream.getvalue() == "Hello\nWorld\nLoading:  20%\nDone\n", f"Got: {repr(stream.getvalue())}"
    
    # 3. Multiple sequential carriage returns
    stream.write("Progress: 0%\r")
    stream.write("Progress: 50%\r")
    stream.write("Progress: 100%\n")
    assert stream.getvalue() == "Hello\nWorld\nLoading:  20%\nDone\nProgress: 100%\n", f"Got: {repr(stream.getvalue())}"
    
    print("✓ LogCapturingStream tests passed successfully!")

def test_stderr_tee():
    print("Testing StderrTee...")
    
    # Save original stderr
    orig_stderr = sys.stderr
    
    # Setup tee
    tee = StderrTee(sys.stderr)
    sys.stderr = tee
    
    captured = []
    def log_callback(data):
        captured.append(data)
        
    tee.set_callback(log_callback)
    
    # Write to sys.stderr
    sys.stderr.write("Test message 1\n")
    sys.stderr.write("Test message 2\n")
    
    tee.clear_callback()
    sys.stderr.write("Test message 3 (should not be captured)\n")
    
    # Restore stderr
    sys.stderr = orig_stderr
    
    assert "Test message 1\n" in captured
    assert "Test message 2\n" in captured
    assert "Test message 3 (should not be captured)\n" not in captured
    
    print("✓ StderrTee tests passed successfully!")

if __name__ == "__main__":
    test_log_capturing_stream()
    test_stderr_tee()
    print("All stream validation tests passed successfully!")
