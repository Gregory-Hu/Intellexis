# workbench/core/workflow/step_result.py
"""
步骤结果 - 基础设施
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum


class LearningLevel(Enum):
    """AI学习水平"""
    NOT_UNDERSTOOD = "not_understood"  # 完全没理解
    BASIC_UNDERSTANDING = "basic"      # 基本理解
    GOOD_UNDERSTANDING = "good"        # 良好掌握
    MASTERED = "mastered"              # 精通掌握


@dataclass
class KnowledgePoint:
    """知识点掌握情况"""
    concept: str                    # 概念
    understanding: LearningLevel   # 理解程度
    confidence: float              # 置信度 (0-1)
    evidence: List[str]            # 证据（AI的推理或代码）
    feedback: Optional[str] = None # 工程师的反馈


@dataclass
class TeachingResult:
    """教学结果"""
    step_id: str
    step_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 教学成果
    knowledge_gained: List[KnowledgePoint] = field(default_factory=list)
    ai_response: str = ""  # AI的回应或生成的代码
    assessment: str = ""   # 对AI表现的评估
    
    # 执行信息
    success: bool = True
    error_message: Optional[str] = None
    execution_time: float = 0.0
    
    # 下一步建议
    next_steps: List[str] = field(default_factory=list)
    recommended_practice: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "timestamp": self.timestamp.isoformat(),
            "knowledge_gained": [
                {
                    "concept": kp.concept,
                    "understanding": kp.understanding.value,
                    "confidence": kp.confidence,
                    "evidence": kp.evidence,
                    "feedback": kp.feedback
                }
                for kp in self.knowledge_gained
            ],
            "ai_response": self.ai_response,
            "assessment": self.assessment,
            "success": self.success,
            "error_message": self.error_message,
            "execution_time": self.execution_time,
            "next_steps": self.next_steps,
            "recommended_practice": self.recommended_practice
        }