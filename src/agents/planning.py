# src/agents/task_agent.py
from typing import List, Dict, Any
from src.world_model import EngineeringWorld
from src.lib.skills import SkillRegistry
from src.lib.sops import SOPS

class TaskAgent:
    """任务执行智能体"""
    
    def __init__(self, world: EngineeringWorld):
        self.world = world
        self.skill_registry = SkillRegistry()
        self.sops = SOPS()
        
        # 执行历史
        self.execution_history = []
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个任务"""
        task_id = task.get("id", str(uuid.uuid4()))
        skill_name = task.get("skill")
        params = task.get("params", {})
        
        # 记录开始
        self.execution_history.append({
            "task_id": task_id,
            "skill": skill_name,
            "start_time": datetime.now().isoformat(),
            "status": "running"
        })
        
        # 执行Skill
        skill = self.skill_registry.get(skill_name)
        if not skill:
            result = {"success": False, "error": f"Skill not found: {skill_name}"}
        else:
            # 参数验证
            if not skill.validate_params(params):
                result = {"success": False, "error": "Invalid parameters"}
            else:
                result = skill.execute(self.world, params)
        
        # 记录结果
        self.execution_history[-1].update({
            "end_time": datetime.now().isoformat(),
            "status": "success" if result.get("success") else "failed",
            "result": result
        })
        
        return result
    
    def execute_sop(self, sop_name: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行SOP流程"""
        sop = self.sops.get(sop_name)
        if not sop:
            return [{"success": False, "error": f"SOP not found: {sop_name}"}]
        
        results = []
        for step in sop["steps"]:
            # 参数模板渲染（MVP阶段简单实现）
            task = {
                "skill": step["skill"],
                "params": self._render_params(step.get("params_template", {}), context)
            }
            result = self.execute_task(task)
            results.append(result)
            
            # 如果某一步失败，可以中断流程（MVP简单策略）
            if not result.get("success"):
                break
        
        return results
    
    def _render_params(self, template: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """简单的参数模板渲染"""
        import json
        template_str = json.dumps(template)
        for key, value in context.items():
            template_str = template_str.replace(f"{{{{ {key} }}}}", str(value))
        return json.loads(template_str)