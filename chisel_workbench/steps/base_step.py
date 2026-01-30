# workbench/core/workflow/step_base.py
"""
步骤基类 - 基础设施，工程师不需要直接使用
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import inspect
from enum import Enum


class StepType(Enum):
    """步骤类型"""
    TEACHING = "teaching"        # 教学步骤
    ANALYSIS = "analysis"        # 分析步骤
    VALIDATION = "validation"    # 验证步骤
    GENERATION = "generation"    # 生成步骤
    DEBUGGING = "debugging"      # 调试步骤
    REVIEW = "review"            # 评审步骤


@dataclass
class TeachingPoint:
    """教学要点 - 工程师教给AI的知识点"""
    concept: str                    # 概念名称
    explanation: str                # 解释说明
    example: Optional[str] = None   # 示例代码
    why_important: str = ""         # 为什么重要
    common_mistakes: List[str] = field(default_factory=list)  # 常见错误
    best_practices: List[str] = field(default_factory=list)   # 最佳实践


@dataclass
class StepConfig:
    """步骤配置"""
    name: str                       # 步骤名称（人类可读）
    description: str                # 步骤描述
    step_type: StepType            # 步骤类型
    version: str = "1.0.0"         # 版本号
    author: str = ""               # 作者
    tags: List[str] = field(default_factory=list)  # 标签
    difficulty: str = "medium"     # 难度等级
    
    # 教学相关配置
    teaching_points: List[TeachingPoint] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)  # 前置知识
    expected_outcome: str = ""     # 期望结果
    
    # 执行配置
    timeout_seconds: int = 300
    max_retries: int = 3


class BaseStep(ABC):
    """步骤基类"""
    
    def __init__(self, config: StepConfig):
        self.config = config
        self.step_id = f"{config.step_type.value}_{uuid.uuid4().hex[:8]}"
        self._execution_context: Dict[str, Any] = {}
        
    @abstractmethod
    async def teach(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        教学AI - 工程师在这里教AI如何做某事
        
        Args:
            context: 执行上下文，包含当前状态和输入
            
        Returns:
            Dict: 教学结果，包含学到的知识和下一步指导
        """
        pass
    
    def explain(self) -> str:
        """向工程师解释这个步骤在教什么"""
        teaching_summary = []
        for tp in self.config.teaching_points:
            teaching_summary.append(f"• {tp.concept}: {tp.explanation}")
        
        return f"""
        步骤名称: {self.config.name}
        教学目的: {self.config.description}
        
        教学要点:
        {chr(10).join(teaching_summary)}
        
        期望结果: {self.config.expected_outcome}
        """
    
    def validate_context(self, context: Dict[str, Any]) -> bool:
        """验证上下文是否适合教学"""
        required_keys = ["project_state", "student_level"]
        return all(key in context for key in required_keys)
    
    def get_teaching_plan(self) -> Dict[str, Any]:
        """获取教学计划"""
        return {
            "step_id": self.step_id,
            "name": self.config.name,
            "description": self.config.description,
            "teaching_points": [
                {
                    "concept": tp.concept,
                    "explanation": tp.explanation,
                    "example": tp.example
                }
                for tp in self.config.teaching_points
            ],
            "prerequisites": self.config.prerequisites,
            "expected_outcome": self.config.expected_outcome,
            "difficulty": self.config.difficulty,
            "estimated_time": self.config.timeout_seconds
        }