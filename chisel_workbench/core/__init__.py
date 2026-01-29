"""
工作台核心框架
"""

from .workbench_context import (
    WorkbenchContext,
    WorkbenchConfig,
    ContextEvent,
    ContextEventType,
    ComponentRegistry
)

from .workbench import (
    Workbench,
    WorkbenchError,
    WorkflowNotFoundError,
    StepExecutionError,
    ValidationError,
    DependencyError
)

# 方便导入的别名
WB = Workbench
WBC = WorkbenchContext

__version__ = "0.1.0"
__all__ = [
    # 上下文
    "WorkbenchContext",
    "WorkbenchConfig",
    "ContextEvent",
    "ContextEventType",
    "ComponentRegistry",
    
    # 工作台
    "Workbench",
    "WorkbenchError",
    "WorkflowNotFoundError",
    "StepExecutionError",
    "ValidationError",
    "DependencyError",
    
    # 别名
    "WB",
    "WBC",
]