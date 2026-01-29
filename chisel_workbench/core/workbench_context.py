"""
WorkbenchContext - 工作台全局上下文管理
管理工作流会话、组件实例和系统配置
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set, Callable, Awaitable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
import pickle

from .state_models import (
    WorkflowSessionState, 
    WorkflowSnapshot,
    CurrentStepState,
    WorkflowStatus,
    StepType,
    ExecutionResult
)

# ============ 上下文事件定义 ============

class ContextEventType(str, Enum):
    """上下文事件类型"""
    SESSION_CREATED = "session_created"
    SESSION_LOADED = "session_loaded"
    SESSION_SAVED = "session_saved"
    SESSION_CLOSED = "session_closed"
    
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_PAUSED = "step_paused"
    
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    
    CHECKPOINT_CREATED = "checkpoint_created"
    SNAPSHOT_CREATED = "snapshot_created"
    
    STATE_CHANGED = "state_changed"
    CONFIG_CHANGED = "config_changed"

@dataclass
class ContextEvent:
    """上下文事件"""
    event_type: ContextEventType
    source: str  # 事件来源组件名称
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    step_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "session_id": self.session_id,
            "step_id": self.step_id
        }

# ============ 上下文配置 ============

@dataclass
class WorkbenchConfig:
    """工作台配置"""
    # 存储配置
    storage_backend: str = "local"  # local, redis, postgres
    storage_path: Path = Path("./.workbench_storage")
    
    # 缓存配置
    cache_enabled: bool = True
    cache_max_size: int = 1000
    cache_ttl_seconds: int = 3600
    
    # 执行配置
    max_concurrent_steps: int = 5
    default_timeout_seconds: int = 300
    auto_save_interval: int = 60  # 自动保存间隔（秒）
    
    # AI 配置
    llm_provider: str = "openai"  # openai, deepseek, anthropic, etc.
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_default_model: str = "gpt-4"
    
    # 日志配置
    log_level: str = "INFO"
    log_file: Optional[Path] = None
    
    # UI 配置
    ui_enabled: bool = True
    ui_host: str = "localhost"
    ui_port: int = 8000
    
    def validate(self) -> List[str]:
        """验证配置，返回错误列表"""
        errors = []
        
        if not self.storage_path:
            errors.append("storage_path is required")
        
        if self.max_concurrent_steps < 1:
            errors.append("max_concurrent_steps must be >= 1")
            
        if self.llm_provider == "openai" and not self.llm_api_key:
            errors.append("llm_api_key is required for OpenAI provider")
            
        return errors
    
    def save(self, path: Path):
        """保存配置到文件"""
        with open(path, 'w') as f:
            json.dump(self.__dict__, f, indent=2, default=str)
    
    @classmethod
    def load(cls, path: Path) -> 'WorkbenchConfig':
        """从文件加载配置"""
        with open(path, 'r') as f:
            data = json.load(f)
        
        # 转换特殊类型
        if 'storage_path' in data:
            data['storage_path'] = Path(data['storage_path'])
        if 'log_file' in data and data['log_file']:
            data['log_file'] = Path(data['log_file'])
            
        return cls(**data)

# ============ 组件注册表 ============

class ComponentRegistry:
    """组件注册表 - 管理所有可用组件"""
    
    def __init__(self):
        self._step_executors: Dict[StepType, Any] = {}  # 步骤执行器
        self._validators: Dict[str, Any] = {}  # 验证器
        self._exporters: Dict[str, Any] = {}  # 导出器
        self._analyzers: Dict[str, Any] = {}  # 分析器
        self._hooks: Dict[str, List[Callable]] = {}  # 钩子函数
        
    def register_step_executor(self, step_type: StepType, executor_class):
        """注册步骤执行器"""
        self._step_executors[step_type] = executor_class
        
    def get_step_executor(self, step_type: StepType):
        """获取步骤执行器"""
        return self._step_executors.get(step_type)
    
    def register_validator(self, name: str, validator_class):
        """注册验证器"""
        self._validators[name] = validator_class
        
    def get_validator(self, name: str):
        """获取验证器"""
        return self._validators.get(name)
    
    def register_hook(self, hook_type: str, callback: Callable):
        """注册钩子函数"""
        if hook_type not in self._hooks:
            self._hooks[hook_type] = []
        self._hooks[hook_type].append(callback)
        
    def trigger_hook(self, hook_type: str, *args, **kwargs):
        """触发钩子函数"""
        results = []
        for callback in self._hooks.get(hook_type, []):
            try:
                result = callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logging.warning(f"Hook {hook_type} failed: {e}")
        return results

# ============ 工作台上下文 ============

class WorkbenchContext:
    """
    工作台上下文 - 管理整个工作台的全局状态和组件实例
    这是单例模式，确保整个应用只有一个上下文实例
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化工作台上下文（单例）"""
        if self._initialized:
            return
            
        self.config: Optional[WorkbenchConfig] = None
        self.logger: Optional[logging.Logger] = None
        
        # 核心状态
        self._current_session: Optional[WorkflowSessionState] = None
        self._sessions: Dict[str, WorkflowSessionState] = {}
        self._active_executions: Set[str] = set()
        
        # 组件实例
        self.registry = ComponentRegistry()
        self._executor = None
        self._storage = None
        self._cache = None
        self._snapshot_manager = None
        self._checkpoint_manager = None
        self._dependency_resolver = None
        
        # 事件系统
        self._event_handlers: Dict[ContextEventType, List[Callable]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        
        # 运行时状态
        self._is_initialized = False
        self._is_shutting_down = False
        self._startup_time = datetime.utcnow()
        
        self._initialized = True
    
    # ============ 初始化与生命周期 ============
    
    async def initialize(self, config: WorkbenchConfig):
        """初始化工作台"""
        if self._is_initialized:
            self.logger.warning("Workbench already initialized")
            return
            
        # 验证配置
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid config: {', '.join(errors)}")
            
        self.config = config
        
        # 初始化日志
        self._setup_logging()
        
        # 初始化存储
        await self._initialize_storage()
        
        # 初始化缓存
        await self._initialize_cache()
        
        # 初始化管理器
        await self._initialize_managers()
        
        # 启动事件处理器
        asyncio.create_task(self._event_processor())
        
        # 启动自动保存任务
        if config.auto_save_interval > 0:
            asyncio.create_task(self._auto_save_task())
        
        self._is_initialized = True
        self.logger.info("Workbench initialized successfully")
        
        # 触发初始化完成事件
        await self.emit_event(ContextEvent(
            event_type=ContextEventType.CONFIG_CHANGED,
            source="workbench",
            data={"config": config.__dict__}
        ))
    
    async def shutdown(self):
        """关闭工作台"""
        if not self._is_initialized or self._is_shutting_down:
            return
            
        self._is_shutting_down = True
        self.logger.info("Shutting down workbench...")
        
        # 停止所有活动执行
        for execution_id in list(self._active_executions):
            await self._cancel_execution(execution_id)
        
        # 保存当前会话
        if self._current_session:
            await self.save_session(self._current_session)
        
        # 关闭组件
        if self._storage:
            await self._storage.close()
        
        if self._cache:
            await self._cache.close()
        
        # 停止事件处理器
        await self._event_queue.put(None)  # 发送停止信号
        
        self._is_initialized = False
        self.logger.info("Workbench shutdown completed")
    
    # ============ 会话管理 ============
    
    def create_session(self, name: str, created_by: str, **kwargs) -> WorkflowSessionState:
        """创建新会话"""
        from .state_models import StateFactory
        
        session = StateFactory.create_workflow_session(
            name=name,
            created_by=created_by,
            **kwargs
        )
        
        self._sessions[str(session.id)] = session
        self._current_session = session
        
        # 触发事件
        asyncio.create_task(self.emit_event(ContextEvent(
            event_type=ContextEventType.SESSION_CREATED,
            source="workbench",
            session_id=str(session.id),
            data={"session_name": name, "created_by": created_by}
        )))
        
        return session
    
    async def load_session(self, session_id: str) -> Optional[WorkflowSessionState]:
        """加载会话"""
        if session_id in self._sessions:
            session = self._sessions[session_id]
        else:
            # 从存储加载
            session = await self._storage.load_session(session_id)
            if session:
                self._sessions[session_id] = session
        
        if session:
            self._current_session = session
            
            # 触发事件
            await self.emit_event(ContextEvent(
                event_type=ContextEventType.SESSION_LOADED,
                source="workbench",
                session_id=session_id
            ))
        
        return session
    
    async def save_session(self, session: WorkflowSessionState):
        """保存会话"""
        session.updated_at = datetime.utcnow()
        
        # 保存到内存
        self._sessions[str(session.id)] = session
        
        # 保存到存储
        if self._storage:
            await self._storage.save_session(session)
        
        # 触发事件
        await self.emit_event(ContextEvent(
            event_type=ContextEventType.SESSION_SAVED,
            source="workbench",
            session_id=str(session.id)
        ))
    
    def close_session(self, session_id: str):
        """关闭会话"""
        if session_id in self._sessions:
            session = self._sessions.pop(session_id)
            
            # 如果关闭的是当前会话，清空当前会话
            if self._current_session and str(self._current_session.id) == session_id:
                self._current_session = None
            
            # 触发事件
            asyncio.create_task(self.emit_event(ContextEvent(
                event_type=ContextEventType.SESSION_CLOSED,
                source="workbench",
                session_id=session_id
            )))
    
    # ============ 属性访问 ============
    
    @property
    def current_session(self) -> Optional[WorkflowSessionState]:
        """获取当前会话"""
        return self._current_session
    
    @current_session.setter
    def current_session(self, session: WorkflowSessionState):
        """设置当前会话"""
        self._current_session = session
    
    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._is_initialized
    
    @property
    def is_running(self) -> bool:
        """检查是否有活动执行"""
        return len(self._active_executions) > 0
    
    # ============ 事件系统 ============
    
    def register_event_handler(self, event_type: ContextEventType, handler: Callable):
        """注册事件处理器"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    async def emit_event(self, event: ContextEvent):
        """发射事件"""
        await self._event_queue.put(event)
    
    async def _event_processor(self):
        """事件处理器协程"""
        while not self._is_shutting_down:
            try:
                event = await self._event_queue.get()
                if event is None:  # 停止信号
                    break
                    
                # 调用注册的处理器
                handlers = self._event_handlers.get(event.event_type, [])
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        self.logger.error(f"Event handler failed: {e}")
                        
                self._event_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Event processor error: {e}")
    
    # ============ 私有方法 ============
    
    def _setup_logging(self):
        """设置日志"""
        self.logger = logging.getLogger("workbench")
        self.logger.setLevel(getattr(logging, self.config.log_level))
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 文件处理器（如果配置了）
        if self.config.log_file:
            file_handler = logging.FileHandler(self.config.log_file)
            file_handler.setFormatter(console_formatter)
            self.logger.addHandler(file_handler)
    
    async def _initialize_storage(self):
        """初始化存储"""
        backend = self.config.storage_backend
        
        if backend == "local":
            from .storage.local_storage import LocalStorage
            self._storage = LocalStorage(self.config.storage_path)
        elif backend == "redis":
            from .storage.redis_storage import RedisStorage
            self._storage = RedisStorage()
        else:
            raise ValueError(f"Unsupported storage backend: {backend}")
        
        await self._storage.initialize()
        self.logger.info(f"Storage initialized: {backend}")
    
    async def _initialize_cache(self):
        """初始化缓存"""
        if not self.config.cache_enabled:
            self.logger.info("Cache disabled")
            return
            
        from .cache.result_cache import ResultCache
        self._cache = ResultCache(
            max_size=self.config.cache_max_size,
            ttl_seconds=self.config.cache_ttl_seconds
        )
        await self._cache.initialize()
        self.logger.info("Cache initialized")
    
    async def _initialize_managers(self):
        """初始化管理器"""
        # 这些将在后续实现
        self._executor = None  # IncrementalExecutor()
        self._snapshot_manager = None  # SnapshotManager()
        self._checkpoint_manager = None  # CheckpointManager()
        self._dependency_resolver = None  # DependencyResolver()
    
    async def _auto_save_task(self):
        """自动保存任务"""
        while not self._is_shutting_down:
            await asyncio.sleep(self.config.auto_save_interval)
            
            if self._current_session:
                try:
                    await self.save_session(self._current_session)
                    self.logger.debug("Auto-saved current session")
                except Exception as e:
                    self.logger.error(f"Auto-save failed: {e}")
    
    async def _cancel_execution(self, execution_id: str):
        """取消执行"""
        # 这里需要根据具体的执行器实现
        self.logger.info(f"Cancelling execution: {execution_id}")
        # TODO: 实现执行取消逻辑