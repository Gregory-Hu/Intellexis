# src/interface/interactive_session.py

class InteractiveSession:
    """人类调试用的对话窗口"""

    def __init__(self, runtime):
        self.runtime = runtime
        self.history = []

    def chat(self):
        print("🧠 Interactive Debug Chat (type 'exit' to quit)")
        while True:
            user_input = input(">> ")
            if user_input.strip().lower() in ("exit", "quit"):
                break

            self.history.append({"role": "user", "content": user_input})
            result = self.runtime.run(user_input)
            self.history.append({"role": "system", "content": result})

            print(f"\n{result}\n")
