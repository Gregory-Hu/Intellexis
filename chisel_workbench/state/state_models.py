"""
状态管理层的核心数据模型
区分不可变状态（用于历史、快照）和可变状态（用于当前编辑和执行）
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union, TypeVar, Generic
from enum import Enum
from pydantic import BaseModel, Field, validator
from uuid import UUID, uuid4

# ============ 基础类型定义 ============

class WorkflowStatus(str, Enum):
    """工作流执行状态"""
    DRAFT = "draft"           # 草稿状态
    PAUSED = "paused"         # 暂停等待人工审核
    RUNNING = "running"       # 正在执行
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消

class StepType(str, Enum):
    """步骤类型"""
    LLM_CALL = "llm_call"           # 调用大模型
    CODE_GENERATION = "code_gen"    # 代码生成
    CODE_VALIDATION = "code_validation"  # 代码验证
    TEST_EXECUTION = "test_execution"    # 测试执行
    DATA_PROCESSING = "data_processing"  # 数据处理
    HUMAN_REVIEW = "human_review"   # 人工审核
    CONDITIONAL = "conditional"     # 条件分支
    PARALLEL = "parallel"           # 并行执行

class ValidationStatus(str, Enum):
    """验证状态"""
    PENDING = "pending"       # 待验证
    PASSED = "passed"         # 通过
    FAILED = "failed"         # 失败
    WARNING = "warning"       # 警告但通过

# ============ 不可变状态模型 ============

class ImmutableBase(BaseModel):
    """不可变模型的基类"""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        frozen = True  # 不可变
        allow_mutation = False

class ExecutionResult(ImmutableBase):
    """单个步骤的执行结果（不可变）"""
    step_id: str
    execution_id: UUID
    output_data: Dict[str, Any]  # 输出数据
    raw_response: Optional[str] = None  # 原始响应（如AI的完整回复）
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # 执行指标
    start_time: datetime
    end_time: datetime
    duration_ms: int
    
    # 资源消耗
    token_usage: Optional[Dict[str, int]] = None  # token消耗
    api_cost: Optional[float] = None  # API成本（美元）
    
    @property
    def successful(self) -> bool:
        """执行是否成功"""
        return not self.output_data.get("error", False)

class StepSnapshot(ImmutableBase):
    """步骤快照（不可变）"""
    step_id: str
    step_type: StepType
    config: Dict[str, Any]  # 步骤配置（如提示词、参数）
    input_data: Dict[str, Any]  # 输入数据
    result: Optional[ExecutionResult] = None  # 执行结果（如果有）
    
    # 验证信息
    validation_status: ValidationStatus = ValidationStatus.PENDING
    validation_notes: Optional[str] = None
    validated_by: Optional[str] = None  # 验证人
    validated_at: Optional[datetime] = None
    
    # 关联关系
    parent_step_id: Optional[str] = None  # 父步骤ID（用于并行或条件分支）
    next_step_id: Optional[str] = None   # 下一个步骤ID

class WorkflowSnapshot(ImmutableBase):
    """工作流快照（不可变）- 用于历史版本、回滚点"""
    snapshot_name: str  # 快照名称
    description: Optional[str] = None
    
    # 工作流定义
    workflow_id: str
    workflow_version: str  # 语义化版本，如"1.0.2"
    step_snapshots: List[StepSnapshot]  # 所有步骤的快照
    
    # 全局状态
    global_variables: Dict[str, Any] = Field(default_factory=dict)
    environment: Dict[str, str] = Field(default_factory=dict)
    
    # 执行上下文
    status: WorkflowStatus
    current_step_index: int  # 当前执行到的步骤索引
    
    # 元数据
    tags: List[str] = Field(default_factory=list)
    
    @property
    def total_duration_ms(self) -> int:
        """计算总执行时间"""
        if not self.step_snapshots:
            return 0
        # 找到最早开始和最晚结束的时间
        start_times = [s.result.start_time for s in self.step_snapshots if s.result]
        end_times = [s.result.end_time for s in self.step_snapshots if s.result]
        
        if not start_times or not end_times:
            return 0
            
        total_start = min(start_times)
        total_end = max(end_times)
        return int((total_end - total_start).total_seconds() * 1000)

# ============ 可变状态模型 ============

class MutableBase(BaseModel):
    """可变模型的基类"""
    id: UUID = Field(default_factory=uuid4)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        validate_assignment = True  # 赋值时进行验证

class CurrentStepState(MutableBase):
    """当前步骤的实时状态（可变）"""
    step_id: str
    step_type: StepType
    
    # 配置（可修改）
    config: Dict[str, Any] = Field(default_factory=dict)
    
    # 执行状态
    status: WorkflowStatus = WorkflowStatus.DRAFT
    retry_count: int = 0
    max_retries: int = 3
    
    # 输入/输出（在执行过程中更新）
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    # 执行历史（最近几次执行结果）
    execution_history: List[ExecutionResult] = Field(default_factory=list)
    
    # 人工干预
    requires_human_review: bool = False
    human_feedback: Optional[str] = None
    approved: Optional[bool] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    
    # 缓存信息
    cache_key: Optional[str] = None  # 用于结果缓存的键
    cache_hit: bool = False
    
    @property
    def current_result(self) -> Optional[ExecutionResult]:
        """获取最新的执行结果"""
        if self.execution_history:
            return self.execution_history[-1]
        return None
    
    @property
    def can_execute(self) -> bool:
        """判断是否可以执行"""
        if self.status in [WorkflowStatus.COMPLETED, WorkflowStatus.RUNNING]:
            return False
        if self.retry_count >= self.max_retries:
            return False
        return True
    
    def add_execution_result(self, result: ExecutionResult):
        """添加执行结果到历史"""
        self.execution_history.append(result)
        self.output_data = result.output_data
        self.updated_at = datetime.utcnow()
        
        # 更新状态
        if result.successful:
            self.status = WorkflowStatus.COMPLETED
            self.error = None
        else:
            self.status = WorkflowStatus.FAILED
            self.error = result.output_data.get("error_message", "Unknown error")
            self.retry_count += 1

class WorkflowSessionState(MutableBase):
    """工作流会话的实时状态（可变）- 当前正在编辑或执行的工作流"""
    # 基础信息
    workflow_name: str
    workflow_description: Optional[str] = None
    
    # 步骤定义和状态
    steps: List[CurrentStepState] = Field(default_factory=list)
    step_dependencies: Dict[str, List[str]] = Field(default_factory=dict)  # 步骤依赖关系
    
    # 全局状态
    global_variables: Dict[str, Any] = Field(default_factory=dict)
    environment_vars: Dict[str, str] = Field(default_factory=dict)
    
    # 执行控制
    status: WorkflowStatus = WorkflowStatus.DRAFT
    current_step_index: int = 0
    auto_proceed: bool = False  # 是否自动继续（不等待人工审核）
    
    # 用户检查点
    user_checkpoints: Dict[str, datetime] = Field(default_factory=dict)  # 检查点名称 -> 创建时间
    
    # 执行统计
    total_api_cost: float = 0.0
    total_token_usage: Dict[str, int] = Field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # 元数据
    created_by: str
    tags: List[str] = Field(default_factory=list)
    project_id: Optional[str] = None
    
    @property
    def current_step(self) -> Optional[CurrentStepState]:
        """获取当前正在执行的步骤"""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    @property
    def completed_steps(self) -> List[CurrentStepState]:
        """获取已完成的步骤"""
        return [s for s in self.steps if s.status == WorkflowStatus.COMPLETED]
    
    @property
    def pending_steps(self) -> List[CurrentStepState]:
        """获取待执行的步骤"""
        return [s for s in self.steps if s.status not in 
                [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]]
    
    def create_checkpoint(self, name: str):
        """创建用户检查点"""
        self.user_checkpoints[name] = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def jump_to_checkpoint(self, checkpoint_name: str):
        """跳转到指定检查点"""
        if checkpoint_name not in self.user_checkpoints:
            raise ValueError(f"Checkpoint '{checkpoint_name}' not found")
        
        # 这里实际实现需要更复杂的逻辑，根据检查点恢复状态
        # 简化版本：重置到某个状态
        checkpoint_time = self.user_checkpoints[checkpoint_name]
        
        # 标记检查点之后的所有步骤为待执行
        for step in self.steps:
            if step.updated_at > checkpoint_time:
                step.status = WorkflowStatus.DRAFT
                step.output_data = None
                step.error = None
        
        self.current_step_index = 0
        self.status = WorkflowStatus.PAUSED
        self.updated_at = datetime.utcnow()
    
    def create_snapshot(self, snapshot_name: str) -> WorkflowSnapshot:
        """创建不可变的快照"""
        step_snapshots = []
        
        for step_state in self.steps:
            step_snapshot = StepSnapshot(
                step_id=step_state.step_id,
                step_type=step_state.step_type,
                config=step_state.config.copy(),
                input_data=step_state.input_data.copy(),
                result=step_state.current_result,
                validation_status=(
                    ValidationStatus.PASSED if step_state.approved
                    else ValidationStatus.PENDING
                ),
                validated_by=step_state.approved_by,
                validated_at=step_state.approved_at,
            )
            step_snapshots.append(step_snapshot)
        
        return WorkflowSnapshot(
            snapshot_name=snapshot_name,
            workflow_id=str(self.id),
            workflow_version="1.0.0",  # 实际应该从版本管理获取
            step_snapshots=step_snapshots,
            global_variables=self.global_variables.copy(),
            environment=self.environment_vars.copy(),
            status=self.status,
            current_step_index=self.current_step_index,
            tags=self.tags.copy(),
        )

# ============ 缓存相关模型 ============

class CachedResult(ImmutableBase):
    """缓存的结果条目（不可变）"""
    cache_key: str  # 通常是步骤类型+输入数据的哈希
    step_type: StepType
    input_signature: str  # 输入数据的签名（用于验证缓存是否有效）
    output_data: Dict[str, Any]
    
    # 命中统计
    hit_count: int = 0
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    
    # 缓存策略
    ttl_seconds: Optional[int] = None  # 生存时间
    priority: int = 1  # 缓存优先级（1-10）
    
    @property
    def is_expired(self) -> bool:
        """检查缓存是否过期"""
        if self.ttl_seconds is None:
            return False
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.ttl_seconds
    
    def record_hit(self):
        """记录一次缓存命中"""
        self.last_accessed = datetime.utcnow()
        # 注意：由于是不可变模型，实际使用中需要特殊处理

# ============ 事件和日志模型 ============

class WorkflowEvent(ImmutableBase):
    """工作流事件（不可变）- 用于审计日志"""
    event_type: str
    workflow_id: UUID
    step_id: Optional[str] = None
    
    # 事件数据
    old_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    
    # 上下文
    triggered_by: str  # 触发者（user_id 或 system）
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    @property
    def is_state_change(self) -> bool:
        """是否是状态变更事件"""
        return self.old_state is not None and self.new_state is not None

# ============ 工厂函数和工具类 ============

class StateFactory:
    """状态对象的工厂类"""
    
    @staticmethod
    def create_step_state(
        step_id: str,
        step_type: StepType,
        config: Dict[str, Any],
        requires_human_review: bool = False
    ) -> CurrentStepState:
        """创建步骤状态"""
        return CurrentStepState(
            step_id=step_id,
            step_type=step_type,
            config=config,
            requires_human_review=requires_human_review,
            status=WorkflowStatus.DRAFT,
        )
    
    @staticmethod
    def create_workflow_session(
        name: str,
        created_by: str,
        steps: Optional[List[CurrentStepState]] = None
    ) -> WorkflowSessionState:
        """创建工作流会话"""
        return WorkflowSessionState(
            workflow_name=name,
            created_by=created_by,
            steps=steps or [],
            status=WorkflowStatus.DRAFT,
        )
    
    @staticmethod
    def create_execution_result(
        step_id: str,
        output_data: Dict[str, Any],
        start_time: datetime,
        end_time: datetime,
        **kwargs
    ) -> ExecutionResult:
        """创建执行结果"""
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        return ExecutionResult(
            step_id=step_id,
            execution_id=uuid4(),
            output_data=output_data,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            **kwargs
        )

# ============ 类型别名和辅助类型 ============

T = TypeVar('T')

class PaginatedList(Generic[T], BaseModel):
    """分页列表"""
    items: List[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    
    @property
    def total_pages(self) -> int:
        """总页数"""
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

# 导出主要类型
__all__ = [
    # 枚举
    'WorkflowStatus',
    'StepType',
    'ValidationStatus',
    
    # 不可变模型
    'ImmutableBase',
    'ExecutionResult',
    'StepSnapshot',
    'WorkflowSnapshot',
    'CachedResult',
    'WorkflowEvent',
    
    # 可变模型
    'MutableBase',
    'CurrentStepState',
    'WorkflowSessionState',
    
    # 工厂和工具
    'StateFactory',
    'PaginatedList',
]