from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Optional, Any, Dict, List
import tempfile
import time
import logging
from pathlib import Path
from datetime import datetime

from base_agent import BaseAgent  
from chant_agent import ChatAgent

# ========== Agent State/Data Define ==========
class AgentState(Enum):
    IDLE = auto()
    RUNNING = auto()
    DONE = auto()
    ERROR = auto()

@dataclass
class SkillMemory:
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_base: Dict[str, Any] = field(default_factory=dict)
    checkpoints: Dict[str, Any] = field(default_factory=dict)

    def record_execution(self, record: Dict[str, Any]):
        self.execution_history.append(record)

@dataclass
class TaskSnapshot:
    task_description: str
    skills_list: List[str] = field(default_factory=list)
    upstream_deliverables: Dict[str, Any] = field(default_factory=dict)
    delivery_criteria: Dict[str, Any] = field(default_factory=dict)
    task_context: Dict[str, Any] = field(default_factory=dict)
    invocation_time: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

@dataclass
class RuntimeState:
    state: AgentState = AgentState.IDLE
    current_task: Optional[str] = None
    task_snapshot: Optional[TaskSnapshot] = None
    current_step: Optional[str] = None
    step_progress: float = 0.0
    error: Optional[str] = None

@dataclass
class AlignmentEvent:
    reason: str                       # 为什么要打断
    report: str                       # AI 当前理解 & 状态
    questions: List[str]              # 需要人类回答的问题
    human_responses: Dict[str, Any] = field(default_factory=dict)
    aligned_understanding: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ========== Logger Setup ==========
logger = logging.getLogger(__name__)


# ========== Skill Agent Implementation ==========
class SkillAgent:
    """
    Skill Agent：负责执行具体任务

        每个 Skill Agent 有自己的工作目录

        每个 Skill Agent 具备：
            - 专有上下文记忆
            - Base Agent推理引擎
    """


    def __init__(
        self,
        agent_id: str,
        skill_name: str,
        base_workspace: Optional[str] = None,
    ):    
        self.agent_id = agent_id
        self.skill_name = skill_name

        # === Workspace ===
        self.work_directory = self._setup_workspace(base_workspace)

        # === Runtime ===
        self.runtime = RuntimeState()

        # === Memory ===
        self.memory = SkillMemory()

        # === Reasoning Engine ===
        self.base_agent = BaseAgent(
            agent_id=f"{agent_id}_base",
            agent_type="reasoning",
            memory_size=1000,
        )

        # === Metrics ===
        self.metrics = {
            "total_runs": 0,
            "avg_execution_time": 0.0,
        }

        logger.info(
            f"SkillAgent [{self.agent_id}] initialized at {self.work_directory}"
        )

    # ------------------------
    # Workspace
    # ------------------------
    def _setup_workspace(self, base_workspace: Optional[str]) -> Path:
        root = (
            Path(base_workspace).expanduser().resolve()
            if base_workspace
            else Path(tempfile.gettempdir()) / "skill_agents"
        )

        root.mkdir(parents=True, exist_ok=True)
        workdir = root / self.agent_id
        workdir.mkdir(parents=True, exist_ok=True)

        for sub in ("logs", "data", "cache"):
            (workdir / sub).mkdir(exist_ok=True)

        return workdir    

        """
            TODO : add source project bashrc
        """

    # ------------------------
    # Public API
    # ------------------------

    def run(
        self, 
        task: str, 
        invocation_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        
        """
        SkillAgent 的唯一对外执行入口
        """
        if self.runtime.state == AgentState.RUNNING:
            raise RuntimeError("SkillAgent is already running")

        invocation_data = invocation_data or {}
        self._enter_run(task, invocation_data)

        start_time = time.time()

        try:
            result = self._execute(task)
            self._exit_run(success=True, result=result)
            return result

        except Exception as e:
            self._exit_run(success=False, error=str(e))
            raise

        finally:
            elapsed = time.time() - start_time
            self._update_metrics(elapsed)   


    def _execute(self, task: str) -> Any:
        """
        实际技能逻辑（子类可 override）
        """
        snapshot = self.runtime.task_snapshot
        prompt = self._build_prompt(task, snapshot)

        response = self.base_agent.run(prompt)
        return response

    def _build_prompt(self, task: str, snapshot: Optional[TaskSnapshot]) -> str:
        if snapshot is None:
            snapshot_info = "No task snapshot available."
        else:
            snapshot_dict = asdict(snapshot)
            snapshot_info = "\n".join(f"{k}: {v}" for k, v in snapshot_dict.items())
        
        prompt = f"""
                  You are a skill agent named '{self.skill_name}'.
  
                  Task:
                  {task}
  
                  Task Snapshot:
                  {snapshot_info}
                  """            
        return prompt
    
    # ------------------------
    # Human Collaboration
    # ------------------------
    def request_alignment(
        self,
        reason: str,
        report: str,
        questions: List[str],
    ) -> AlignmentEvent:
        chat_agent = ChatAgent(
            agent_id=f"{self.agent_id}_chat_{len(self.memory.execution_history)}"
        )

        event = AlignmentEvent(
            reason=reason,
            report=report,
            questions=questions,
        )

        aligned_event = chat_agent.start_alignment(event)

        # 记录到 memory（非常重要）
        self.memory.checkpoints["alignment"] = aligned_event

        return aligned_event


    # ------------------------
    # Lifecycle
    # ------------------------
    def _enter_run(self, task: str, invocation_data: Dict[str, Any]):
        self.runtime.state = AgentState.RUNNING
        self.runtime.current_task = task
        self.runtime.error = None

        self.runtime.task_snapshot = TaskSnapshot(
            task_description=invocation_data.get("task_description", task),
            skills_list=invocation_data.get("skills_list", []),
            upstream_deliverables=invocation_data.get(
                "upstream_deliverables", {}
            ),
            delivery_criteria=invocation_data.get(
                "delivery_criteria", {}
            ),
            task_context=invocation_data.get("task_context", {}),
        )

    def _exit_run(
            self,
            success: bool,
            result: Any = None,
            error: Optional[str] = None,
        ):
            self.runtime.state = AgentState.DONE if success else AgentState.ERROR
            self.runtime.error = error

            # 记录完整快照到memory（关键价值点）
            self.memory.record_execution(
                {
                    "task": self.runtime.current_task,
                    "snapshot": asdict(self.runtime.task_snapshot) if self.runtime.task_snapshot else {},
                    "success": success,
                    "result": result,
                    "error": error,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            self.runtime.current_task = None
            self.runtime.current_step = None
            self.runtime.step_progress = 0.0
            self.runtime.task_snapshot = None
    
    # ------------------------
    # Metrics
    # ------------------------

    def _update_metrics(self, elapsed: float):
        self.metrics["total_runs"] += 1
        n = self.metrics["total_runs"]
        self.metrics["avg_execution_time"] = (
            (self.metrics["avg_execution_time"] * (n - 1) + elapsed) / n
        )