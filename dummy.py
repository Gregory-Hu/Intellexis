# workbench/steps/examples/dummy_step.py
"""
DummyStep - 最简单的教学步骤示例
用于演示和测试
"""
import asyncio
import time
from typing import Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from ....core.state_models import WorkbenchState


@dataclass
class StepConfig:
    """步骤配置"""
    name: str = "Dummy Step"
    description: str = "This is a dummy step for testing"
    step_type: str = "teaching"
    version: str = "1.0.0"
    difficulty: str = "easy"
    timeout_seconds: int = 10


@dataclass
class TeachingResult:
    """教学结果"""
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat()
        }


class DummyStep:
    """
    DummyStep - 最简单的教学步骤
    
    这个步骤不做实际工作，只是用来演示：
    1. 如何创建一个教学步骤
    2. 如何与工作台交互
    3. 如何返回教学结果
    """
    
    config = StepConfig()
    
    def __init__(self, config: StepConfig = None):
        self.config = config or self.config
        self.step_id = f"dummy_{int(time.time())}"
    
    async def teach(self, state: WorkbenchState, inputs: Dict[str, Any], context: Dict[str, Any]) -> TeachingResult:
        """
        教学AI - 这是步骤的主要执行方法
        
        Args:
            state: 当前工作台状态
            inputs: 输入参数
            context: 执行上下文
            
        Returns:
            TeachingResult: 教学结果
        """
        start_time = time.time()
        
        print(f"🤖 DummyStep开始教学...")
        print(f"   步骤名称: {self.config.name}")
        print(f"   输入参数: {inputs}")
        print(f"   项目: {state.current_project.project_id if state.current_project else '无项目'}")
        
        # 模拟一些教学逻辑
        await asyncio.sleep(0.5)  # 模拟教学时间
        
        # 创建一些教学结果数据
        knowledge_gained = [
            {
                "concept": "虚拟概念1",
                "understanding": "basic",
                "confidence": 0.8
            },
            {
                "concept": "虚拟概念2", 
                "understanding": "good",
                "confidence": 0.9
            }
        ]
        
        # 模拟AI的回应
        ai_response = "我理解了！虚拟概念用于教学演示，真实步骤需要具体芯片设计知识。"
        
        execution_time = time.time() - start_time
        
        print(f"✅ DummyStep教学完成!")
        print(f"   教学时间: {execution_time:.2f}秒")
        print(f"   AI学会了 {len(knowledge_gained)} 个概念")
        
        return TeachingResult(
            success=True,
            message=f"DummyStep '{self.config.name}' 执行成功",
            data={
                "step_id": self.step_id,
                "step_name": self.config.name,
                "knowledge_gained": knowledge_gained,
                "ai_response": ai_response,
                "execution_context": {
                    "project_id": state.current_project.project_id if state.current_project else None,
                    "workflow_id": context.get("workflow_id", "unknown"),
                    "execution_time": execution_time
                },
                "next_steps": ["real_chisel_parsing", "code_analysis"]
            },
            execution_time=execution_time
        )
    
    def explain(self) -> str:
        """解释这个步骤在教什么"""
        return f"""
        步骤名称: {self.config.name}
        
        教学目的: {self.config.description}
        
        这是一个虚拟步骤，用于演示如何：
        1. 创建教学步骤
        2. 与工作台状态交互
        3. 返回结构化的教学结果
        
        真实的教学步骤应该包含：
        - 具体的芯片设计知识
        - Chisel3代码分析
        - AI学习评估
        """


# 简化的HelloStep
class HelloStep(DummyStep):
    """打招呼步骤"""
    
    def __init__(self):
        config = StepConfig(
            name="Hello Step",
            description="教AI如何打招呼和介绍自己",
            step_type="introduction",
            difficulty="very_easy"
        )
        super().__init__(config)
    
    async def teach(self, state: WorkbenchState, inputs: Dict[str, Any], context: Dict[str, Any]) -> TeachingResult:
        start_time = time.time()
        
        print("👋 HelloStep: 教AI打招呼...")
        
        # 获取用户名
        username = inputs.get("username", "工程师")
        
        # 模拟AI学习打招呼
        greeting = f"你好{username}！我是芯片设计AI助手，很高兴为你服务。"
        
        execution_time = time.time() - start_time
        
        return TeachingResult(
            success=True,
            message="AI学会了如何打招呼",
            data={
                "greeting": greeting,
                "username": username,
                "step_type": "introduction",
                "learned_concepts": ["打招呼", "自我介绍"]
            },
            execution_time=execution_time
        )


# 简化的EchoStep
class EchoStep(DummyStep):
    """回声步骤 - 返回输入的内容"""
    
    def __init__(self):
        config = StepConfig(
            name="Echo Step", 
            description="教AI如何回应输入",
            step_type="interaction",
            difficulty="easy"
        )
        super().__init__(config)
    
    async def teach(self, state: WorkbenchState, inputs: Dict[str, Any], context: Dict[str, Any]) -> TeachingResult:
        start_time = time.time()
        
        print("🔄 EchoStep: 教AI如何回应...")
        
        # 获取输入消息
        message = inputs.get("message", "你好")
        
        # 模拟AI学习回应
        response = f"我收到你的消息: '{message}'。这是一个测试回应。"
        
        execution_time = time.time() - start_time
        
        return TeachingResult(
            success=True,
            message="AI学会了如何回应输入",
            data={
                "original_message": message,
                "ai_response": response,
                "step_type": "interaction",
                "response_time": execution_time
            },
            execution_time=execution_time
        )