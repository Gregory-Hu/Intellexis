# ==================== 核心数据模型 ====================
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime
from enum import Enum
import json
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor

class AgentState(Enum):
    """Skill Agent状态枚举"""
    RUNNING = "running"          # 正在执行任务
    PAUSED = "paused"            # 暂停，等待对齐
    COMPLETED = "completed"      # 任务完成
    ERROR = "error"              # 执行错误
    WAITING_FOR_ALIGNMENT = "waiting_for_alignment"  # 等待对齐完成

class ChatbotIntent(Enum):
    """Chatbot对话意图"""
    CLARIFY = "clarify"           # 澄清问题
    APPROVE = "approve"           # 批准/确认
    DISCUSS = "discuss"          # 讨论方案
    PROVIDE_FEEDBACK = "provide_feedback"  # 提供反馈
    CONTINUE_EXECUTION = "continue_execution"  # 继续执行
    REQUEST_CHANGE = "request_change"  # 请求变更

@dataclass
class SkillContext:
    """Skill Agent传递给Chatbot的上下文"""
    task_id: str
    task_name: str
    agent_state: AgentState
    checkpoint: Dict[str, Any]  # 检查点信息
    alignment_needs: List[Dict[str, Any]]  # 需要对齐的内容
    progress_summary: Dict[str, Any]  # 进度摘要
    metadata: Dict[str, Any] = None
    
    def to_dict(self):
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "agent_state": self.agent_state.value,
            "checkpoint": self.checkpoint,
            "alignment_needs": self.alignment_needs,
            "progress_summary": self.progress_summary,
            "metadata": self.metadata or {}
        }

@dataclass
class ChatbotOutput:
    """Chatbot返回给Skill Agent的输出"""
    session_id: str
    original_context: SkillContext  # 原始上下文
    alignment_results: Dict[str, Any]  # 对齐结果
    human_feedback: List[Dict[str, Any]]  # 人类反馈
    continuation_decision: Dict[str, Any]  # 继续执行决策
    extracted_knowledge: Dict[str, Any]  # 提取的知识/信息
    
    def to_dict(self):
        return {
            "session_id": self.session_id,
            "original_context": self.original_context.to_dict(),
            "alignment_results": self.alignment_results,
            "human_feedback": self.human_feedback,
            "continuation_decision": self.continuation_decision,
            "extracted_knowledge": self.extracted_knowledge
        }

@dataclass
class DialogueTurn:
    """对话轮次"""
    turn_id: str
    speaker: str  # "human" or "chatbot"
    message: str
    timestamp: str
    metadata: Dict[str, Any] = None

@dataclass 
class ChatbotMemory:
    """Chatbot对话记忆"""
    context: SkillContext
    dialogue_history: List[DialogueTurn]
    alignment_points: Dict[str, Dict]  # 对齐点ID -> 对齐点详情
    resolved_points: List[str]  # 已解决的对齐点ID
    session_start_time: str
    session_end_time: Optional[str] = None
    
    def to_dict(self):
        return {
            "context": self.context.to_dict(),
            "dialogue_history": [turn.__dict__ for turn in self.dialogue_history],
            "alignment_points": self.alignment_points,
            "resolved_points": self.resolved_points,
            "session_duration": self._calculate_duration()
        }
    
    def _calculate_duration(self):
        if self.session_end_time:
            start = datetime.fromisoformat(self.session_start_time)
            end = datetime.fromisoformat(self.session_end_time)
            return int((end - start).total_seconds())
        return 0


# ==================== Skill Agent 核心 ====================


