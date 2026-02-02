
class ModelingAgent:
    """建模智能体 - 感知世界、更新模型"""
    
    def __init__(self, skill_registry: SkillRegistry):
        self.skills = skill_registry
        self.perception_cache = {}  # 感知缓存
        
    def perceive_and_update(self, world: EngineeringWorld) -> PerceptionReport:
        """感知世界并更新模型"""
        # 调用各种感知技能（如parse_code、analyze_dependencies）
        # 更新world中的结构化信息
        pass

# src/agents/planning/planning_agent.py  
class PlanningAgent:
    """规划智能体 - 将目标拆解为可执行任务"""
    
    def plan(self, 
             goal: Goal, 
             world: EngineeringWorld,
             available_sops: List[SOP]) -> ExecutionPlan:
        """
        制定执行计划
        
        规则：
        1. 只能读取world，不能修改
        2. 只能建议，不执行
        3. 输出必须是机器可执行的计划
        """
        pass