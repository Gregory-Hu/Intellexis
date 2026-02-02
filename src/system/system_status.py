# src/system/system_status.py
from enum import Enum

class SystemStatus(Enum):
    CREATED = "created"
    MODELING = "modeling"
    MODELED = "modeled"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
