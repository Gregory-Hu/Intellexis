# src/system/runtime_system.py
import uuid
from datetime import datetime
from planning_agent import PlanningAgent
from orchestrator_agent import OrchestratorAgent
from system_status import SystemStatus
from execution_runtime import ExecutionRuntime

class RuntimeSystem:
    """世界已建成后的运行系统"""

    def __init__(self, bootstrap):
        if bootstrap.status != SystemStatus.MODELED:
            raise RuntimeError("World not modeled yet")

        # self.skill_registry = bootstrap.skill_registry
        # self.sop_registry = bootstrap.sop_registry

        # self.planning_agent = PlanningAgent(self.sop_registry)
        # self.orchestrator_agent = OrchestratorAgent(self.skill_registry)

        self.status = SystemStatus.READY

    def create_runtime(self) -> ExecutionRuntime:
        if self.status != SystemStatus.READY:
            raise RuntimeError("System not ready")

        self.status = SystemStatus.RUNNING

        return ExecutionRuntime(
            system=self,
            session_id=str(uuid.uuid4()),
            created_at=datetime.now()
        )
