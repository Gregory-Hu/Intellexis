# src/world_model/__init__.py
class EngineeringWorld:
    def __init__(self):
        self.modules = {}           # 模块信息
        self.files = {}             # 文件信息
        self.simulation_status = None  # 仿真状态
        self.history = []           # 操作历史记录
        self._observers = []        # 观察者列表（用于事件通知）
    
    def add_observer(self, observer):
        self._observers.append(observer)
    
    def notify_observers(self, event_type, data):
        for observer in self._observers:
            observer.on_world_update(event_type, data)