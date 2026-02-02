# src/agents/modeling_agent.py
from typing import Dict, Any
from src.world_model import EngineeringWorld
from src.lib.skills import SkillRegistry

class ModelingAgent:
    """Project World Model Builder and maintainer"""
    
    def __init__(self, world: EngineeringWorld):
        self.world = world
        self.skill_registry = SkillRegistry()
        
        # 订阅世界模型更新
        world.add_observer(self)
    
    def on_world_update(self, event_type: str, data: Dict[str, Any]):
        """处理世界模型更新事件"""
        if event_type == "file_modified":
            self._update_file_model(data["file_path"])
        elif event_type == "simulation_completed":
            self._update_simulation_model(data)
    
    def _update_file_model(self, file_path: str):
        """更新文件模型"""
        try:
            # 调用解析Skill来分析文件内容
            parse_skill = self.skill_registry.get("parse_verilog")
            if parse_skill:
                result = parse_skill.execute(self.world, {"file_path": file_path})
                if result["success"]:
                    self.world.modules[result["module_name"]] = result["module_info"]
        except Exception as e:
            print(f"Failed to update file model: {e}")
    
    def build_initial_world(self, project_root: str):
        """构建初始世界模型"""
        # 扫描项目目录
        scan_skill = self.skill_registry.get("scan_directory")
        if scan_skill:
            result = scan_skill.execute(self.world, {"directory": project_root})
            if result["success"]:
                for file_info in result["files"]:
                    self._update_file_model(file_info["path"])