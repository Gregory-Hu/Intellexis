class ChatAgent:
    """
    ChatAgent = 人类 Copilot 对齐代理
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    def start_alignment(self, event: AlignmentEvent) -> AlignmentEvent:
        """
        这里假设是阻塞式（MVP）
        真实系统中可以接 UI / IM / API
        """

        # 1. 汇报
        print("\n=== 汇报 ===")
        print(event.report)

        # 2. 请示
        print("\n=== 请示 ===")
        responses = {}
        for q in event.questions:
            responses[q] = input(f"{q}\n> ")

        event.human_responses = responses

        # 3. 对齐理解（由 AI 总结）
        print("\n=== 对齐理解 ===")
        summary = self._summarize_alignment(event)
        print(summary)

        confirm = input("\n是否确认理解无误？(y/n) > ")
        if confirm.lower() != "y":
            raise RuntimeError("Alignment not confirmed by human")

        event.aligned_understanding = summary
        return event

    def _summarize_alignment(self, event: AlignmentEvent) -> str:
        """
        MVP：简单拼接
        后续可用 LLM 总结
        """
        lines = ["基于沟通，我的理解是："]
        for q, a in event.human_responses.items():
            lines.append(f"- {q}: {a}")
        return "\n".join(lines)
