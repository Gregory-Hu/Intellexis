
# ==================== Alignment Chatbot 核心 ====================
class AlignmentChatbot:
    """对齐聊天机器人：负责与人类对话，收集反馈"""
    
    def __init__(self, chatbot_id: str, llm_client=None):
        self.chatbot_id = chatbot_id
        self.llm_client = llm_client
        self.active_sessions = {}  # session_id -> ChatbotMemory
        self.agent_callbacks = {}  # session_id -> 回调函数
        
        # 对话模板
        self.templates = {
            "greeting": "您好！我是对齐助手。Skill Agent在执行任务时需要与您对齐一些内容。",
            "alignment_needs": "以下是需要与您对齐的内容：\n{alignment_needs}",
            "clarification": "关于'{point}'，您能提供更多细节或澄清一下吗？",
            "approval_request": "请问您是否批准这个方案？",
            "summary": "根据我们的对话，我已经记录了以下信息：\n{summary}",
            "continuation_prompt": "如果您确认对齐已完成，请告诉我'继续执行'。"
        }
    
    async def start_alignment_session(self, context: SkillContext, continuation_callback: Callable) -> str:
        """启动对齐会话
        
        Args:
            context: Skill Agent传递的上下文
            continuation_callback: 对齐完成后的回调函数，用于通知Skill Agent继续执行
            
        Returns:
            session_id: 对齐会话ID
        """
        session_id = f"align_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 初始化记忆
        memory = ChatbotMemory(
            context=context,
            dialogue_history=[],
            alignment_points=self._extract_alignment_points(context.alignment_needs),
            resolved_points=[],
            session_start_time=datetime.now().isoformat()
        )
        
        self.active_sessions[session_id] = memory
        self.agent_callbacks[session_id] = continuation_callback
        
        print(f"💬 [Chatbot] 启动对齐会话 {session_id}")
        print(f"📋 [Chatbot] 需要对齐的内容: {len(context.alignment_needs)}项")
        
        # 生成初始问候和需要对齐的内容
        initial_message = await self._generate_initial_message(context)
        
        # 记录对话
        self._add_dialogue_turn(session_id, "chatbot", initial_message)
        
        return session_id, initial_message
    
    async def process_human_input(self, session_id: str, human_input: str) -> Dict[str, Any]:
        """处理人类输入
        
        Args:
            session_id: 会话ID
            human_input: 人类输入文本
            
        Returns:
            包含Chatbot响应和会话状态的字典
        """
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        memory = self.active_sessions[session_id]
        
        # 记录人类输入
        self._add_dialogue_turn(session_id, "human", human_input)
        
        # 检查是否为继续执行指令
        if self._is_continuation_command(human_input):
            return await self._handle_continuation_request(session_id, human_input)
        
        # 分析人类输入意图
        intent = await self._analyze_intent(human_input, memory)
        
        # 根据意图生成响应
        chatbot_response = await self._generate_response(intent, human_input, memory)
        
        # 更新对齐点状态
        self._update_alignment_points(session_id, intent, human_input)
        
        # 记录Chatbot响应
        self._add_dialogue_turn(session_id, "chatbot", chatbot_response)
        
        # 检查是否所有对齐点都已解决
        alignment_complete = self._check_alignment_completion(session_id)
        
        return {
            "session_id": session_id,
            "chatbot_response": chatbot_response,
            "intent": intent.value,
            "alignment_status": {
                "total_points": len(memory.alignment_points),
                "resolved_points": len(memory.resolved_points),
                "all_resolved": alignment_complete
            },
            "continuation_suggested": alignment_complete
        }
    
    async def _handle_continuation_request(self, session_id: str, human_input: str) -> Dict[str, Any]:
        """处理继续执行请求"""
        memory = self.active_sessions[session_id]
        
        # 生成会话摘要
        session_summary = await self._generate_session_summary(session_id)
        
        # 提取知识
        extracted_knowledge = self._extract_knowledge_from_dialogue(memory)
        
        # 创建Chatbot输出
        chatbot_output = ChatbotOutput(
            session_id=session_id,
            original_context=memory.context,
            alignment_results={
                "resolved_points": memory.resolved_points,
                "remaining_points": list(set(memory.alignment_points.keys()) - set(memory.resolved_points))
            },
            human_feedback=self._extract_feedback_from_dialogue(memory),
            continuation_decision={
                "action": "continue",
                "reason": "Human requested continuation",
                "timestamp": datetime.now().isoformat()
            },
            extracted_knowledge=extracted_knowledge
        )
        
        # 标记会话结束
        memory.session_end_time = datetime.now().isoformat()
        
        # 调用回调函数通知Skill Agent
        if session_id in self.agent_callbacks:
            continuation_callback = self.agent_callbacks[session_id]
            await continuation_callback(chatbot_output)
        
        # 清理会话
        self._end_session(session_id)
        
        return {
            "session_id": session_id,
            "chatbot_response": "✅ 对齐完成！我已通知Skill Agent继续执行。",
            "intent": "continuation_confirmed",
            "session_summary": session_summary,
            "action": "session_ended"
        }
    
    async def _generate_initial_message(self, context: SkillContext) -> str:
        """生成初始消息"""
        # 如果有LLM，可以使用LLM生成更自然的问候
        if self.llm_client:
            try:
                prompt = f"""
                作为对齐助手，你需要向人类工程师介绍Skill Agent当前的状态和需要对齐的内容。
                
                Skill Agent状态：
                - 任务：{context.task_name}
                - 当前状态：{context.agent_state.value}
                - 需要对齐的内容：{len(context.alignment_needs)}项
                
                请生成一个专业、友好的问候，简要说明情况并邀请工程师参与对齐。
                """
                
                response = await self.llm_client.generate(prompt, max_tokens=200)
                return response.strip()
            except:
                pass
        
        # 回退到模板
        alignment_needs_text = "\n".join([
            f"{i+1}. {need.get('description', '未描述')} ({need.get('type', 'unknown')})"
            for i, need in enumerate(context.alignment_needs)
        ])
        
        return (
            f"{self.templates['greeting']}\n\n"
            f"当前任务：{context.task_name}\n"
            f"需要对齐的内容：\n{alignment_needs_text}\n\n"
            f"请逐一检查这些内容，并提供您的反馈。"
        )
    
    async def _analyze_intent(self, text: str, memory: ChatbotMemory) -> ChatbotIntent:
        """分析人类输入意图"""
        text_lower = text.lower()
        
        # 如果有LLM，使用LLM分析意图
        if self.llm_client:
            try:
                prompt = f"""
                分析以下用户输入的意图：
                
                用户输入："{text}"
                
                当前上下文：
                - 任务：{memory.context.task_name}
                - 待解决对齐点：{len(memory.alignment_points) - len(memory.resolved_points)}个
                
                可选意图：
                {[intent.value for intent in ChatbotIntent]}
                
                请选择最匹配的意图，并简要说明理由。
                输出格式：意图|理由
                """
                
                response = await self.llm_client.generate(prompt, max_tokens=100)
                
                if "|" in response:
                    intent_str, _ = response.split("|", 1)
                    intent_str = intent_str.strip()
                    
                    for intent in ChatbotIntent:
                        if intent.value == intent_str:
                            return intent
            except:
                pass
        
        # 回退到基于规则的意图识别
        if any(word in text_lower for word in ["澄清", "解释", "说明", "clarify", "explain"]):
            return ChatbotIntent.CLARIFY
        elif any(word in text_lower for word in ["同意", "批准", "确认", "approve", "confirm"]):
            return ChatbotIntent.APPROVE
        elif any(word in text_lower for word in ["建议", "提议", "suggest", "propose"]):
            return ChatbotIntent.DISCUSS
        elif any(word in text_lower for word in ["反馈", "意见", "feedback"]):
            return ChatbotIntent.PROVIDE_FEEDBACK
        elif any(word in text_lower for word in ["继续", "执行", "continue", "resume"]):
            return ChatbotIntent.CONTINUE_EXECUTION
        elif any(word in text_lower for word in ["修改", "更改", "调整", "change", "modify"]):
            return ChatbotIntent.REQUEST_CHANGE
        else:
            # 默认视为讨论
            return ChatbotIntent.DISCUSS
    
    async def _generate_response(self, intent: ChatbotIntent, human_input: str, memory: ChatbotMemory) -> str:
        """根据意图生成响应"""
        
        # 如果有LLM，使用LLM生成响应
        if self.llm_client:
            try:
                prompt = self._build_llm_prompt(intent, human_input, memory)
                response = await self.llm_client.generate(prompt, max_tokens=300)
                return response.strip()
            except:
                pass
        
        # 回退到模板响应
        if intent == ChatbotIntent.CLARIFY:
            return "我理解您需要澄清。您具体想了解哪个方面的细节？"
        elif intent == ChatbotIntent.APPROVE:
            return "收到您的批准。请问您批准的是哪个具体方案？"
        elif intent == ChatbotIntent.DISCUSS:
            # 获取一个未解决的对齐点进行讨论
            unresolved = self._get_unresolved_point(memory)
            if unresolved:
                return f"我们正在讨论：{unresolved.get('description', '')}。您有什么想法或建议？"
            else:
                return "感谢您的意见。还有其他需要讨论的内容吗？"
        elif intent == ChatbotIntent.PROVIDE_FEEDBACK:
            return "感谢您的反馈！我会记录下来并传递给Skill Agent。"
        elif intent == ChatbotIntent.CONTINUE_EXECUTION:
            return "您希望继续执行吗？请确认所有对齐点都已解决。"
        elif intent == ChatbotIntent.REQUEST_CHANGE:
            return "了解您希望进行修改。请具体说明需要修改的内容。"
        else:
            return "我理解了您的输入。能具体说明一下您的需求吗？"
    
    def _build_llm_prompt(self, intent: ChatbotIntent, human_input: str, memory: ChatbotMemory) -> str:
        """构建LLM提示词"""
        
        unresolved_points = [
            point for point_id, point in memory.alignment_points.items()
            if point_id not in memory.resolved_points
        ]
        
        prompt = f"""
        你是一个对齐助手，正在与人类工程师讨论Skill Agent的执行情况。
        
        当前任务：{memory.context.task_name}
        任务状态：{memory.context.agent_state.value}
        
        需要对齐的内容（{len(unresolved_points)}项待解决）：
        {self._format_alignment_points(unresolved_points)}
        
        对话历史（最近3条）：
        {self._format_recent_history(memory)}
        
        工程师最新输入："{human_input}"
        识别的意图：{intent.value}
        
        请生成一个专业、有帮助的响应，继续推进对齐过程。
        如果有未解决的对齐点，可以引导工程师关注其中一个。
        如果所有对齐点都已解决，可以建议继续执行。
        
        响应要求：
        1. 保持友好和专业
        2. 回应工程师的具体输入
        3. 推进对齐过程
        4. 如果合适，可以询问具体问题
        5. 使用中文回复
        
        请生成响应：
        """
        
        return prompt
    
    def _format_alignment_points(self, points: List[Dict]) -> str:
        """格式化对齐点显示"""
        if not points:
            return "无"
        
        formatted = []
        for i, point in enumerate(points, 1):
            formatted.append(f"{i}. [{point.get('type', 'unknown')}] {point.get('description', '未描述')}")
        
        return "\n".join(formatted)
    
    def _format_recent_history(self, memory: ChatbotMemory) -> str:
        """格式化最近对话历史"""
        if not memory.dialogue_history:
            return "无"
        
        recent = memory.dialogue_history[-3:]  # 最近3条
        formatted = []
        for turn in recent:
            speaker = "工程师" if turn.speaker == "human" else "助手"
            formatted.append(f"{speaker}: {turn.message[:100]}")
        
        return "\n".join(formatted)
    
    def _extract_alignment_points(self, alignment_needs: List[Dict[str, Any]]) -> Dict[str, Dict]:
        """从对齐需求中提取对齐点"""
        points = {}
        
        for i, need in enumerate(alignment_needs):
            point_id = f"point_{i+1}_{uuid.uuid4().hex[:6]}"
            points[point_id] = {
                "point_id": point_id,
                "type": need.get("type", "unknown"),
                "description": need.get("description", ""),
                "context": need.get("context", {}),
                "options": need.get("options", []),
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
        
        return points
    
    def _update_alignment_points(self, session_id: str, intent: ChatbotIntent, human_input: str):
        """根据对话更新对齐点状态"""
        memory = self.active_sessions[session_id]
        
        # 简单的状态更新逻辑
        # 在实际应用中，这里应该更智能地判断哪些点被解决了
        if intent in [ChatbotIntent.APPROVE, ChatbotIntent.DISCUSS]:
            # 如果有未解决的点，可以标记为正在讨论
            unresolved = self._get_unresolved_point_id(memory)
            if unresolved:
                memory.alignment_points[unresolved]["status"] = "in_discussion"
    
    def _check_alignment_completion(self, session_id: str) -> bool:
        """检查对齐是否完成"""
        memory = self.active_sessions[session_id]
        
        # 简单的完成条件：所有点都被标记为resolved
        resolved_count = len(memory.resolved_points)
        total_count = len(memory.alignment_points)
        
        # 如果有对话历史，可以更智能地判断
        if len(memory.dialogue_history) >= 5:
            # 对话足够长，可以检查是否讨论了主要问题
            last_few = memory.dialogue_history[-5:]
            human_turns = [t for t in last_few if t.speaker == "human"]
            
            if len(human_turns) >= 2:
                # 人类有足够输入，可能已经完成对齐
                return True
        
        return resolved_count >= total_count * 0.8  # 80%的点已解决
    
    def _get_unresolved_point(self, memory: ChatbotMemory) -> Optional[Dict]:
        """获取一个未解决的对齐点"""
        for point_id, point in memory.alignment_points.items():
            if point_id not in memory.resolved_points:
                return point
        return None
    
    def _get_unresolved_point_id(self, memory: ChatbotMemory) -> Optional[str]:
        """获取一个未解决的对齐点ID"""
        for point_id, point in memory.alignment_points.items():
            if point_id not in memory.resolved_points:
                return point_id
        return None
    
    def _add_dialogue_turn(self, session_id: str, speaker: str, message: str):
        """添加对话轮次"""
        if session_id in self.active_sessions:
            turn = DialogueTurn(
                turn_id=f"turn_{len(self.active_sessions[session_id].dialogue_history)}",
                speaker=speaker,
                message=message,
                timestamp=datetime.now().isoformat()
            )
            self.active_sessions[session_id].dialogue_history.append(turn)
    
    def _is_continuation_command(self, text: str) -> bool:
        """检查是否为继续执行命令"""
        continuation_keywords = ["继续执行", "继续", "恢复执行", "可以继续了", "continue", "resume", "proceed"]
        text_lower = text.lower()
        
        for keyword in continuation_keywords:
            if keyword in text_lower:
                return True
        
        return False
    
    async def _generate_session_summary(self, session_id: str) -> Dict[str, Any]:
        """生成会话摘要"""
        memory = self.active_sessions[session_id]
        
        summary = {
            "session_id": session_id,
            "task_name": memory.context.task_name,
            "start_time": memory.session_start_time,
            "end_time": memory.session_end_time,
            "total_turns": len(memory.dialogue_history),
            "human_turns": len([t for t in memory.dialogue_history if t.speaker == "human"]),
            "alignment_points_resolved": len(memory.resolved_points),
            "alignment_points_total": len(memory.alignment_points),
            "key_decisions": self._extract_key_decisions(memory)
        }
        
        return summary
    
    def _extract_key_decisions(self, memory: ChatbotMemory) -> List[str]:
        """从对话中提取关键决策"""
        decisions = []
        
        # 简单的提取逻辑：查找包含决策关键词的对话
        decision_keywords = ["决定", "决策", "选择", "采用", "approve", "decide", "choose"]
        
        for turn in memory.dialogue_history:
            if turn.speaker == "human":
                for keyword in decision_keywords:
                    if keyword in turn.message:
                        decisions.append(turn.message[:100] + "...")
                        break
        
        return decisions[:5]  # 最多返回5个
    
    def _extract_feedback_from_dialogue(self, memory: ChatbotMemory) -> List[Dict[str, Any]]:
        """从对话中提取人类反馈"""
        feedback_list = []
        
        for turn in memory.dialogue_history:
            if turn.speaker == "human":
                # 简单的反馈分类
                feedback_type = "general"
                
                if any(word in turn.message for word in ["建议", "提议", "suggest"]):
                    feedback_type = "suggestion"
                elif any(word in turn.message for word in ["修正", "纠正", "错误", "correct"]):
                    feedback_type = "correction"
                elif any(word in turn.message for word in ["同意", "批准", "approve"]):
                    feedback_type = "approval"
                
                feedback_list.append({
                    "type": feedback_type,
                    "content": turn.message,
                    "timestamp": turn.timestamp,
                    "description": f"{feedback_type}: {turn.message[:50]}..."
                })
        
        return feedback_list
    
    def _extract_knowledge_from_dialogue(self, memory: ChatbotMemory) -> Dict[str, Any]:
        """从对话中提取知识/信息"""
        knowledge = {
            "human_preferences": [],
            "clarifications": [],
            "constraints": [],
            "suggestions": []
        }
        
        for turn in memory.dialogue_history:
            if turn.speaker == "human":
                # 这里可以更智能地提取知识
                # 现在只是简单分类
                if "喜欢" in turn.message or "偏好" in turn.message:
                    knowledge["human_preferences"].append(turn.message)
                elif "解释" in turn.message or "说明" in turn.message:
                    knowledge["clarifications"].append(turn.message)
                elif "不能" in turn.message or "限制" in turn.message:
                    knowledge["constraints"].append(turn.message)
                elif "建议" in turn.message:
                    knowledge["suggestions"].append(turn.message)
        
        return knowledge
    
    def _end_session(self, session_id: str):
        """结束会话并清理"""
        if session_id in self.active_sessions:
            # 可以保存会话记录到数据库
            session_data = self.active_sessions[session_id].to_dict()
            print(f"📁 [Chatbot] 保存会话记录: {session_id}")
            
            # 清理
            del self.active_sessions[session_id]
            if session_id in self.agent_callbacks:
                del self.agent_callbacks[session_id]


# ==================== 协调器 ====================
class SkillCoordinator:
    """协调器：管理Skill Agent和Chatbot的交互"""
    
    def __init__(self):
        self.skill_agents = {}  # agent_id -> SkillAgent
        self.alignment_chatbot = None
        self.active_sessions = {}  # task_id -> 会话信息
    
    def register_skill_agent(self, agent: SkillAgent):
        """注册Skill Agent"""
        self.skill_agents[agent.agent_id] = agent
        agent.register_alignment_callback(self.handle_alignment_request)
        print(f"🔄 [Coordinator] 注册Skill Agent: {agent.agent_id}")
    
    def set_alignment_chatbot(self, chatbot: AlignmentChatbot):
        """设置Alignment Chatbot"""
        self.alignment_chatbot = chatbot
        print(f"🔄 [Coordinator] 设置Alignment Chatbot: {chatbot.chatbot_id}")
    
    async def handle_alignment_request(self, context: SkillContext) -> ChatbotOutput:
        """处理对齐请求（从Skill Agent调用）"""
        print(f"🔄 [Coordinator] 收到对齐请求，任务: {context.task_name}")
        
        if not self.alignment_chatbot:
            raise Exception("No alignment chatbot available")
        
        # 启动Chatbot对齐会话
        session_id, initial_message = await self.alignment_chatbot.start_alignment_session(
            context=context,
            continuation_callback=self.handle_alignment_completion
        )
        
        # 存储会话信息
        self.active_sessions[session_id] = {
            "task_id": context.task_id,
            "agent_id": None,  # 需要找到对应的Agent
            "context": context,
            "start_time": datetime.now().isoformat(),
            "status": "active"
        }
        
        # 这里可以通知前端或人类工程师开始对齐
        print(f"💬 [Coordinator] 对齐会话 {session_id} 已启动")
        print(f"  初始消息: {initial_message[:100]}...")
        
        # 等待对齐完成
        # 在实际实现中，这里可能通过事件或回调来等待
        # 为了简化，我们假设通过一个Future来等待
        completion_event = asyncio.Event()
        self.active_sessions[session_id]["completion_event"] = completion_event
        self.active_sessions[session_id]["result"] = None
        
        # 等待对齐完成
        await completion_event.wait()
        
        # 获取对齐结果
        result = self.active_sessions[session_id]["result"]
        
        if not result:
            raise Exception("Alignment completed but no result")
        
        # 清理会话
        del self.active_sessions[session_id]
        
        return result
    
    async def handle_alignment_completion(self, chatbot_output: ChatbotOutput):
        """处理对齐完成（从Chatbot调用）"""
        session_id = chatbot_output.session_id
        
        print(f"🔄 [Coordinator] 对齐会话 {session_id} 完成")
        
        if session_id in self.active_sessions:
            # 存储结果并通知等待的Skill Agent
            self.active_sessions[session_id]["result"] = chatbot_output
            
            # 触发完成事件
            if "completion_event" in self.active_sessions[session_id]:
                self.active_sessions[session_id]["completion_event"].set()
    
    async def forward_human_input(self, session_id: str, human_input: str) -> Dict[str, Any]:
        """转发人类输入到Chatbot"""
        if not self.alignment_chatbot:
            return {"error": "No alignment chatbot available"}
        
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        # 处理人类输入
        result = await self.alignment_chatbot.process_human_input(session_id, human_input)
        
        return result


# ==================== 使用示例 ====================
async def main():
    """使用示例"""
    
    # 1. 创建协调器
    coordinator = SkillCoordinator()
    
    # 2. 创建Skill Agent
    skill_agent = SkillAgent(agent_id="data_analyzer_001", skill_name="数据分析")
    
    # 3. 创建Alignment Chatbot（可以传入LLM客户端）
    chatbot = AlignmentChatbot(chatbot_id="alignment_helper_001")
    
    # 4. 注册到协调器
    coordinator.register_skill_agent(skill_agent)
    coordinator.set_alignment_chatbot(chatbot)
    
    # 5. 定义任务
    task = {
        "id": "task_001",
        "name": "用户行为数据分析",
        "steps": [
            {
                "name": "数据收集",
                "type": "data_processing",
                "has_ambiguity": False
            },
            {
                "name": "数据清洗",
                "type": "data_processing",
                "has_ambiguity": True,  # 需要对齐
                "requires_alignment": [
                    {
                        "type": "ambiguity_resolution",
                        "description": "如何处理缺失值",
                        "context": {"data_size": 10000, "missing_rate": 0.05},
                        "options": ["删除缺失值", "使用均值填充", "使用中位数填充"]
                    }
                ]
            },
            {
                "name": "分析执行",
                "type": "decision_making",
                "requires_approval": True,  # 需要批准
                "approval_criteria": ["分析方法", "参数设置"]
            },
            {
                "name": "生成报告",
                "type": "code_execution"
            }
        ]
    }
    
    print("=" * 60)
    print("示例：Skill Agent执行任务，遇到需要对齐的点时暂停")
    print("=" * 60)
    
    # 6. 异步执行任务
    import threading
    
    def run_skill_agent():
        """在单独的线程中运行Skill Agent"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def execute():
            result = await skill_agent.execute_task(task)
            print(f"\n🎯 Skill Agent最终结果: {result}")
        
        loop.run_until_complete(execute())
    
    # 启动Skill Agent
    skill_thread = threading.Thread(target=run_skill_agent)
    skill_thread.start()
    
    # 模拟人类与Chatbot的交互
    print("\n模拟人类与Chatbot的交互...")
    
    # 这里可以添加实际的前端界面或CLI交互
    # 为了示例，我们假设有一个简单的CLI交互
    
    # 等待Skill Agent进入对齐状态
    await asyncio.sleep(2)
    
    # 检查是否有活动的对齐会话
    if coordinator.active_sessions:
        session_id = list(coordinator.active_sessions.keys())[0]
        
        # 模拟人类输入
        human_inputs = [
            "你好，我看到需要处理缺失值的问题",
            "我建议使用均值填充，因为数据分布比较均匀",
            "批准这个分析方法",
            "继续执行"
        ]
        
        for human_input in human_inputs:
            print(f"\n🧑‍💼 人类: {human_input}")
            
            # 转发到Chatbot
            result = await coordinator.forward_human_input(session_id, human_input)
            
            if "chatbot_response" in result:
                print(f"🤖 Chatbot: {result['chatbot_response']}")
            
            await asyncio.sleep(1)
    
    # 等待Skill Agent完成
    skill_thread.join()


if __name__ == "__main__":
    asyncio.run(main())