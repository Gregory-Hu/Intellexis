"""
Workbench - 工作台主框架
提供工作流编排、执行、监控的核心API
"""

import asyncio
import inspect
from typing import Dict, List, Optional, Any, Callable, Awaitable, Union
from datetime import datetime
from contextlib import asynccontextmanager
import traceback

from .workbench_context import WorkbenchContext, WorkbenchConfig, ContextEvent, ContextEventType
from .state_models import (
    WorkflowSessionState,
    CurrentStepState,
    WorkflowStatus,
    StepType,
    ExecutionResult,
    StateFactory
)

# ============ 工作台异常 ============

class WorkbenchError(Exception):
    """工作台基础异常"""
    pass

class WorkflowNotFoundError(WorkbenchError):
    """工作流未找到异常"""
    pass

class StepExecutionError(WorkbenchError):
    """步骤执行异常"""
    def __init__(self, step_id: str, message: str, details: Optional[Dict] = None):
        self.step_id = step_id
        self.message = message
        self.details = details or {}
        super().__init__(f"Step '{step_id}' failed: {message}")

class ValidationError(WorkbenchError):
    """验证异常"""
    pass

class DependencyError(WorkbenchError):
    """依赖关系异常"""
    pass

# ============ 工作台主类 ============

class Workbench:
    """
    工作台主类 - 提供工作流编排和执行的核心API
    封装业务逻辑，协调各个组件
    """
    
    def __init__(self, config: Optional[WorkbenchConfig] = None):
        """初始化工作台"""
        self.context = WorkbenchContext()
        self._config = config
        self._is_running = False
        
        # 执行锁，防止并发问题
        self._execution_lock = asyncio.Lock()
        
    # ============ 生命周期管理 ============
    
    async def start(self):
        """启动工作台"""
        if self._is_running:
            return
            
        if not self._config:
            raise WorkbenchError("Config must be provided before starting")
            
        await self.context.initialize(self._config)
        self._is_running = True
        
        # 注册默认事件处理器
        self.context.register_event_handler(
            ContextEventType.STEP_COMPLETED,
            self._handle_step_completed
        )
        self.context.register_event_handler(
            ContextEventType.STEP_FAILED,
            self._handle_step_failed
        )
        
    async def stop(self):
        """停止工作台"""
        if not self._is_running:
            return
            
        await self.context.shutdown()
        self._is_running = False
    
    @asynccontextmanager
    async def session(self):
        """工作台会话上下文管理器"""
        try:
            yield self
        finally:
            await self.stop()
    
    # ============ 工作流管理 ============
    
    async def create_workflow(
        self,
        name: str,
        created_by: str,
        description: Optional[str] = None,
        **kwargs
    ) -> WorkflowSessionState:
        """创建工作流"""
        if not self._is_running:
            raise WorkbenchError("Workbench is not running")
            
        session = self.context.create_session(
            name=name,
            created_by=created_by,
            workflow_description=description,
            **kwargs
        )
        
        await self.context.save_session(session)
        return session
    
    async def load_workflow(self, session_id: str) -> WorkflowSessionState:
        """加载工作流"""
        session = await self.context.load_session(session_id)
        if not session:
            raise WorkflowNotFoundError(f"Workflow {session_id} not found")
        return session
    
    async def save_workflow(self, session: Optional[WorkflowSessionState] = None):
        """保存工作流"""
        if not session:
            session = self.context.current_session
            if not session:
                raise WorkbenchError("No current session to save")
                
        await self.context.save_session(session)
    
    async def delete_workflow(self, session_id: str):
        """删除工作流"""
        # 从内存中移除
        self.context.close_session(session_id)
        
        # 从存储中删除
        if self.context._storage:
            await self.context._storage.delete_session(session_id)
    
    # ============ 步骤管理 ============
    
    async def add_step(
        self,
        step_type: StepType,
        config: Dict[str, Any],
        requires_human_review: bool = False,
        session: Optional[WorkflowSessionState] = None
    ) -> str:
        """添加步骤到工作流"""
        if not session:
            session = self.context.current_session
            if not session:
                raise WorkbenchError("No current session")
        
        step_id = f"step_{len(session.steps) + 1:03d}"
        step_state = StateFactory.create_step_state(
            step_id=step_id,
            step_type=step_type,
            config=config,
            requires_human_review=requires_human_review
        )
        
        session.steps.append(step_state)
        await self.context.save_session(session)
        
        return step_id
    
    async def update_step(
        self,
        step_id: str,
        config: Optional[Dict[str, Any]] = None,
        requires_human_review: Optional[bool] = None,
        session: Optional[WorkflowSessionState] = None
    ):
        """更新步骤配置"""
        if not session:
            session = self.context.current_session
            if not session:
                raise WorkbenchError("No current session")
        
        step = self._find_step(session, step_id)
        if not step:
            raise WorkbenchError(f"Step {step_id} not found")
        
        if config is not None:
            step.config.update(config)
            step.updated_at = datetime.utcnow()
            
        if requires_human_review is not None:
            step.requires_human_review = requires_human_review
        
        await self.context.save_session(session)
    
    async def remove_step(self, step_id: str, session: Optional[WorkflowSessionState] = None):
        """从工作流中移除步骤"""
        if not session:
            session = self.context.current_session
            if not session:
                raise WorkbenchError("No current session")
        
        step_index = self._find_step_index(session, step_id)
        if step_index is None:
            raise WorkbenchError(f"Step {step_id} not found")
        
        # 移除步骤
        session.steps.pop(step_index)
        
        # 更新当前步骤索引
        if session.current_step_index >= step_index:
            session.current_step_index = max(0, session.current_step_index - 1)
        
        await self.context.save_session(session)
    
    # ============ 工作流执行 ============
    
    async def execute_workflow(
        self,
        session_id: Optional[str] = None,
        start_from: Optional[int] = None,
        auto_proceed: Optional[bool] = None
    ) -> str:
        """执行工作流"""
        async with self._execution_lock:
            # 加载会话
            if session_id:
                session = await self.load_workflow(session_id)
                self.context.current_session = session
            else:
                session = self.context.current_session
                if not session:
                    raise WorkbenchError("No current session")
            
            # 更新执行参数
            if start_from is not None:
                session.current_step_index = max(0, min(start_from, len(session.steps) - 1))
            
            if auto_proceed is not None:
                session.auto_proceed = auto_proceed
            
            # 开始执行
            execution_id = f"exec_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            self.context._active_executions.add(execution_id)
            
            # 启动执行任务
            asyncio.create_task(self._execute_workflow_task(session, execution_id))
            
            # 触发事件
            await self.context.emit_event(ContextEvent(
                event_type=ContextEventType.WORKFLOW_STARTED,
                source="workbench",
                session_id=str(session.id),
                data={"execution_id": execution_id}
            ))
            
            return execution_id
    
    async def pause_workflow(self, execution_id: str):
        """暂停工作流执行"""
        # 这里需要与执行器交互，暂时标记状态
        session = self.context.current_session
        if session:
            session.status = WorkflowStatus.PAUSED
            
            await self.context.emit_event(ContextEvent(
                event_type=ContextEventType.WORKFLOW_PAUSED,
                source="workbench",
                session_id=str(session.id),
                data={"execution_id": execution_id}
            ))
    
    async def resume_workflow(self, execution_id: str):
        """恢复工作流执行"""
        # TODO: 实现恢复逻辑
        pass
    
    async def cancel_workflow(self, execution_id: str):
        """取消工作流执行"""
        # 移除执行ID
        if execution_id in self.context._active_executions:
            self.context._active_executions.remove(execution_id)
        
        session = self.context.current_session
        if session:
            session.status = WorkflowStatus.CANCELLED
            
            await self.context.emit_event(ContextEvent(
                event_type=ContextEventType.WORKFLOW_CANCELLED,
                source="workbench",
                session_id=str(session.id),
                data={"execution_id": execution_id}
            ))
    
    # ============ 步骤执行 ============
    
    async def execute_step(
        self,
        step_id: str,
        input_data: Optional[Dict[str, Any]] = None,
        session: Optional[WorkflowSessionState] = None,
        use_cache: bool = True
    ) -> ExecutionResult:
        """执行单个步骤"""
        if not session:
            session = self.context.current_session
            if not session:
                raise WorkbenchError("No current session")
        
        step = self._find_step(session, step_id)
        if not step:
            raise WorkbenchError(f"Step {step_id} not found")
        
        # 检查是否可以执行
        if not step.can_execute:
            raise StepExecutionError(step_id, f"Cannot execute step in status: {step.status}")
        
        # 准备输入数据
        if input_data:
            step.input_data = input_data
        
        # 检查缓存
        if use_cache and self.context._cache and step.cache_key:
            cached_result = await self.context._cache.get(step.cache_key)
            if cached_result:
                step.cache_hit = True
                return cached_result
        
        # 执行步骤
        try:
            result = await self._execute_single_step(step)
            
            # 缓存结果
            if use_cache and self.context._cache:
                await self.context._cache.set(
                    key=step.cache_key or f"{step.step_type}_{hash(str(step.input_data))}",
                    value=result,
                    ttl_seconds=self.context.config.cache_ttl_seconds if self.context.config else 3600
                )
            
            return result
            
        except Exception as e:
            # 创建失败的结果
            result = StateFactory.create_execution_result(
                step_id=step_id,
                output_data={"error": True, "error_message": str(e)},
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow()
            )
            
            step.add_execution_result(result)
            await self.context.save_session(session)
            
            raise StepExecutionError(step_id, str(e), {"traceback": traceback.format_exc()})
    
    # ============ 检查点和快照 ============
    
    async def create_checkpoint(self, name: str, session: Optional[WorkflowSessionState] = None):
        """创建检查点"""
        if not session:
            session = self.context.current_session
            if not session:
                raise WorkbenchError("No current session")
        
        session.create_checkpoint(name)
        await self.context.save_session(session)
        
        await self.context.emit_event(ContextEvent(
            event_type=ContextEventType.CHECKPOINT_CREATED,
            source="workbench",
            session_id=str(session.id),
            data={"checkpoint_name": name}
        ))
    
    async def jump_to_checkpoint(self, checkpoint_name: str, session: Optional[WorkflowSessionState] = None):
        """跳转到检查点"""
        if not session:
            session = self.context.current_session
            if not session:
                raise WorkbenchError("No current session")
        
        session.jump_to_checkpoint(checkpoint_name)
        await self.context.save_session(session)
    
    async def create_snapshot(
        self,
        snapshot_name: str,
        description: Optional[str] = None,
        session: Optional[WorkflowSessionState] = None
    ) -> str:
        """创建快照"""
        if not session:
            session = self.context.current_session
            if not session:
                raise WorkbenchError("No current session")
        
        snapshot = session.create_snapshot(snapshot_name)
        if description:
            snapshot.description = description
        
        # 保存快照
        if self.context._snapshot_manager:
            snapshot_id = await self.context._snapshot_manager.save_snapshot(snapshot)
        else:
            # 临时实现
            snapshot_id = str(snapshot.id)
            if self.context._storage:
                await self.context._storage.save_snapshot(snapshot)
        
        await self.context.emit_event(ContextEvent(
            event_type=ContextEventType.SNAPSHOT_CREATED,
            source="workbench",
            session_id=str(session.id),
            data={
                "snapshot_id": snapshot_id,
                "snapshot_name": snapshot_name
            }
        ))
        
        return snapshot_id
    
    # ============ 查询和监控 ============
    
    async def get_workflow_status(self, session_id: str) -> Dict[str, Any]:
        """获取工作流状态"""
        session = await self.load_workflow(session_id)
        
        return {
            "session_id": str(session.id),
            "name": session.workflow_name,
            "status": session.status,
            "current_step_index": session.current_step_index,
            "total_steps": len(session.steps),
            "completed_steps": len(session.completed_steps),
            "start_time": session.start_time.isoformat() if session.start_time else None,
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "total_api_cost": session.total_api_cost,
            "created_by": session.created_by,
            "updated_at": session.updated_at.isoformat()
        }
    
    async def get_step_history(self, step_id: str, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取步骤执行历史"""
        if session_id:
            session = await self.load_workflow(session_id)
        else:
            session = self.context.current_session
            if not session:
                return []
        
        step = self._find_step(session, step_id)
        if not step:
            return []
        
        history = []
        for result in step.execution_history:
            history.append({
                "execution_id": str(result.execution_id),
                "start_time": result.start_time.isoformat(),
                "end_time": result.end_time.isoformat(),
                "duration_ms": result.duration_ms,
                "successful": result.successful,
                "token_usage": result.token_usage,
                "api_cost": result.api_cost
            })
        
        return history
    
    # ============ 辅助方法 ============
    
    def _find_step(self, session: WorkflowSessionState, step_id: str) -> Optional[CurrentStepState]:
        """查找步骤"""
        for step in session.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def _find_step_index(self, session: WorkflowSessionState, step_id: str) -> Optional[int]:
        """查找步骤索引"""
        for i, step in enumerate(session.steps):
            if step.step_id == step_id:
                return i
        return None
    
    async def _execute_workflow_task(self, session: WorkflowSessionState, execution_id: str):
        """执行工作流的后台任务"""
        try:
            session.start_time = datetime.utcnow()
            session.status = WorkflowStatus.RUNNING
            await self.context.save_session(session)
            
            # 执行所有步骤
            while session.current_step_index < len(session.steps):
                step = session.steps[session.current_step_index]
                
                # 检查是否需要人工审核
                if step.requires_human_review and not step.approved:
                    session.status = WorkflowStatus.PAUSED
                    await self.context.save_session(session)
                    
                    # 等待人工审核
                    # TODO: 实现等待机制
                    break
                
                # 执行步骤
                try:
                    await self._execute_step_in_workflow(step, session)
                except StepExecutionError as e:
                    self.context.logger.error(f"Step {step.step_id} failed: {e}")
                    
                    # 检查是否需要重试
                    if step.retry_count < step.max_retries:
                        step.status = WorkflowStatus.DRAFT
                        continue  # 重试当前步骤
                    else:
                        # 工作流失败
                        session.status = WorkflowStatus.FAILED
                        break
                
                # 移动到下一个步骤
                session.current_step_index += 1
            
            # 更新完成状态
            if session.status == WorkflowStatus.RUNNING:
                session.status = WorkflowStatus.COMPLETED
                session.end_time = datetime.utcnow()
            
            await self.context.save_session(session)
            
            # 触发完成事件
            await self.context.emit_event(ContextEvent(
                event_type=ContextEventType.WORKFLOW_COMPLETED,
                source="workbench",
                session_id=str(session.id),
                data={
                    "execution_id": execution_id,
                    "status": session.status,
                    "total_duration": (session.end_time - session.start_time).total_seconds() if session.end_time else None
                }
            ))
            
        except Exception as e:
            self.context.logger.error(f"Workflow execution failed: {e}")
            session.status = WorkflowStatus.FAILED
            await self.context.save_session(session)
            
        finally:
            # 清理执行ID
            if execution_id in self.context._active_executions:
                self.context._active_executions.remove(execution_id)
    
    async def _execute_step_in_workflow(self, step: CurrentStepState, session: WorkflowSessionState):
        """在工作流中执行单个步骤"""
        # 触发步骤开始事件
        await self.context.emit_event(ContextEvent(
            event_type=ContextEventType.STEP_STARTED,
            source="workbench",
            session_id=str(session.id),
            step_id=step.step_id,
            data={"step_type": step.step_type}
        ))
        
        # 执行步骤
        result = await self.execute_step(step.step_id, session=session)
        
        # 更新会话统计
        if result.token_usage:
            for key, value in result.token_usage.items():
                session.total_token_usage[key] = session.total_token_usage.get(key, 0) + value
        
        if result.api_cost:
            session.total_api_cost += result.api_cost
        
        await self.context.save_session(session)
    
    async def _execute_single_step(self, step: CurrentStepState) -> ExecutionResult:
        """执行单个步骤（实际调用执行器）"""
        start_time = datetime.utcnow()
        
        try:
            # 获取步骤执行器
            executor_class = self.context.registry.get_step_executor(step.step_type)
            if not executor_class:
                raise WorkbenchError(f"No executor for step type: {step.step_type}")
            
            # 创建执行器实例
            executor = executor_class(self.context)
            
            # 执行步骤
            output_data = await executor.execute(step.config, step.input_data)
            
            end_time = datetime.utcnow()
            
            # 创建执行结果
            result = StateFactory.create_execution_result(
                step_id=step.step_id,
                output_data=output_data,
                start_time=start_time,
                end_time=end_time
            )
            
            # 添加到步骤历史
            step.add_execution_result(result)
            
            # 触发步骤完成事件
            await self.context.emit_event(ContextEvent(
                event_type=ContextEventType.STEP_COMPLETED,
                source="workbench",
                step_id=step.step_id,
                data={"successful": True}
            ))
            
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            
            # 触发步骤失败事件
            await self.context.emit_event(ContextEvent(
                event_type=ContextEventType.STEP_FAILED,
                source="workbench",
                step_id=step.step_id,
                data={
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            ))
            
            raise
    
    async def _handle_step_completed(self, event: ContextEvent):
        """处理步骤完成事件"""
        # 可以在这里添加自定义逻辑，如发送通知、更新监控等
        pass
    
    async def _handle_step_failed(self, event: ContextEvent):
        """处理步骤失败事件"""
        # 可以在这里添加自定义逻辑，如发送告警、记录日志等
        pass