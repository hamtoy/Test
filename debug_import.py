try:
    import src.agent

    print(f"src.agent imported: {src.agent}")
    from src.agent import GeminiAgent

    print(f"GeminiAgent imported: {GeminiAgent}")

    from src.agent.core import GeminiAgent as CoreAgent

    print(f"CoreAgent imported: {CoreAgent}")

    assert GeminiAgent is CoreAgent
    print("Assertion passed")
except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
