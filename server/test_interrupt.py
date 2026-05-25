import threading
import time
from mlx_mcp_server import MLXModel, _thread_context

class MockAgent:
    def __init__(self):
        self.interrupt_switch = False

class MockTokenizer:
    def convert_tokens_to_ids(self, *args, **kwargs):
        return 1
    unk_token_id = 0

def mock_stream_generate(model, tokenizer, prompt, **kwargs):
    # Yield some tokens, simulating a slow stream
    for i in range(10):
        time.sleep(0.1)
        # Yield a mock response object that has a .text attribute
        class MockResponse:
            def __init__(self, text):
                self.text = text
        yield MockResponse(f"token_{i} ")

def test_mlx_model_interruption():
    print("Testing MLXModel real-time interruption...")
    
    # 1. Instantiate the MLXModel subclass with dummy model ID
    # We will mock mlx_lm.load to prevent actual downloading during this unit test
    import mlx_lm
    orig_load = mlx_lm.load
    mlx_lm.load = lambda *args, **kwargs: ("dummy_model", MockTokenizer())
    
    model_instance = MLXModel("dummy-id")
    # Mock stream_generate to use our slow mock generator
    model_instance.stream_generate = mock_stream_generate
    
    # Restore original mlx_lm.load
    mlx_lm.load = orig_load

    # 2. Setup active agent and thread context
    agent = MockAgent()
    _thread_context.active_agent = agent

    # 3. Simulate cancellation by setting a timer to flip the interrupt switch mid-generation
    def flip_switch():
        time.sleep(0.35)
        print("[Test Timer] Setting agent.interrupt_switch = True")
        agent.interrupt_switch = True

    timer = threading.Thread(target=flip_switch)
    timer.start()

    # 4. Trigger model generation
    # It should yield 3 tokens, then detect interruption and raise RuntimeError
    try:
        # Mock tokenizer.apply_chat_template to return dummy prompt_ids
        model_instance.tokenizer.apply_chat_template = lambda *args, **kwargs: [1, 2, 3]
        
        # Override _prepare_completion_kwargs to return dummy dict
        model_instance._prepare_completion_kwargs = lambda *args, **kwargs: {
            "messages": [], "stop": [], "tools": None
        }

        print("Starting mock generation...")
        model_instance.generate([])
        assert False, "Error: MLXModel.generate should have been interrupted but completed successfully."
    except RuntimeError as e:
        assert "Generation interrupted by user request" in str(e), f"Unexpected exception: {e}"
        print("✓ Interruption detected in-loop correctly!")

    timer.join()
    # Clean up thread context
    if hasattr(_thread_context, "active_agent"):
        del _thread_context.active_agent
        
    print("All MLXModel interruption tests passed successfully!")

if __name__ == "__main__":
    test_mlx_model_interruption()
