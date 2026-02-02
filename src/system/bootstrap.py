
from registry import SkillRegistry, SopRegistry
from modeling_agent import ModelingAgent
from system_status import SystemStatus

class SystemBootstrap:
    """系统自举阶段：世界建模"""

    def __init__(self, config: dict):
        self.config = config
        self.status = SystemStatus.CREATED

        # self.skill_registry = SkillRegistry()
        # self.sop_registry = SopRegistry()
        # self.modeling_agent = ModelingAgent(self.skill_registry)

    def run_modeling(self):
        if self.status != SystemStatus.CREATED:
            raise RuntimeError("Bootstrap already executed")

        self.status = SystemStatus.MODELING

        # 🔥 核心：让建模智能体“生成世界”
        '''
        self.modeling_agent.build_world(
            config=self.config,
            skill_registry=self.skill_registry,
            sop_registry=self.sop_registry
        )
        '''
        print("World Modeler under implementation")
        print("Mocking Modeling Phase")

        self.status = SystemStatus.MODELED
