
from bootstrap import SystemBootstrap
from runtime_system import RuntimeSystem

class EngineeringSystem:
    """Intellexis Core System"""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)

        self.bootstrap = SystemBootstrap(self.config)
        self.runtime_system = None

    def build(self):
        """🔥 显式建模阶段"""

        # Modeling Phase
        self.bootstrap.run_modeling() 
        
        # Run Time Phase
        self.runtime_system = RuntimeSystem(self.bootstrap)

    def create_runtime(self):
        if not self.runtime_system:
            raise RuntimeError("System not built yet")

        return self.runtime_system.create_runtime()

    def _load_config(self, path: str) -> dict:
        import json
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
