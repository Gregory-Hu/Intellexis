import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid
import hashlib
import tempfile
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

from agent_data_model import AgentState
from agent_work_space import FileSystemTool

class SkillAgent:
    """
    Skill Agent：负责执行具体任务

        每个 Skill Agent 有自己的工作目录

        每个 Skill Agent 具备：
            - 专有上下文记忆
            - Base Agent推理引擎
    """
    def __init__(self, agent_id: str, skill_name: str, base_workspace: Optional[str] = None):
        """
        初始化 Skill Agent

        参数:
            - agent_id: 代理的唯一标识符
            - base_workspace: 工作空间的根目录，如果为None则使用临时目录
        """
        # 参数
        self.agent_id = agent_id
        self.fs_tool = FileSystemTool()

        """
        Wrap into a Method
        Set Up Workspace
        # 设置工作空间
        if base_workspace:
            self.base_workspace = Path(base_workspace).expanduser().resolve()
        else:
            self.base_workspace = Path(tempfile.gettempdir()) / "skill_agents"
        
        # 确保基础工作空间存在
        self.base_workspace.mkdir(parents=True, exist_ok=True)
        
        # 设置当前工作目录
        self.work_directory = self.base_workspace / agent_id
        self.work_directory.mkdir(parents=True, exist_ok=True)
        
        # 初始化日志目录
        self.log_directory = self.work_directory / "logs"
        self.log_directory.mkdir(exist_ok=True)
        
        # 初始化数据目录
        self.data_directory = self.work_directory / "data"
        self.data_directory.mkdir(exist_ok=True)
        
        # 初始化缓存目录
        self.cache_directory = self.work_directory / "cache"
        self.cache_directory.mkdir(exist_ok=True)
        
        logger.info(f"SkillAgent '{agent_id}' 初始化完成，工作目录: {self.work_directory}")           
        """

        # 技能和状态
        self.skill_name = skill_name
        self.state = AgentState.IDLE
        
        # 当前任务执行信息
        self.current_task = None
        self.task_input = None  # 存储任务输入信息
        
        # 执行上下文记忆（专有记忆）
        self.context_memory = {
            "execution_history": [],  # 历史执行记录
            "knowledge_base": {},     # 领域知识记忆
            "checkpoints": {}         # 检查点记忆
        }
        
        # 内置通用Base Agent（核心推理引擎）
        self.base_agent = BaseAgent(
            agent_id=f"{agent_id}_base",
            agent_type="reasoning",
            memory_size=1000
        )
        
        # 对齐回调函数
        self.alignment_callback = None
        
        # 当前执行步骤信息
        self.current_step = None
        self.step_progress = 0
        
        # 线程池用于异步操作
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        # 技能配置
        self.skill_config = {
            "max_retries": 3,
            "timeout_seconds": 300,
            "quality_threshold": 0.8
        }
        
        # 任务状态追踪
        self.task_metrics = {
            "avg_execution_time": 0,
            "alignment_requests": 0
        }
    
    async def invoke(self, invocation_data: dict) -> dict:
        """
        被Manager Agent调用时执行的方法
        
        Args:
            invocation_data: 包含:
                - skills_list: 当前任务所需的技能列表
                - upstream_deliverables: 上游交付件
                - task_description: 任务描述
                - delivery_criteria: 交付标准
                - task_context: 任务上下文信息（可选）
                
        Returns:
            执行结果字典
        """
        try:

            # 重置状态（除上下文记忆外）
            self.state = AgentState.EXECUTING
            self.current_step = None
            self.step_progress = 0
            
            # 存储任务输入
            self.task_input = {
                "skills_list": invocation_data.get("skills_list", []),
                "upstream_deliverables": invocation_data.get("upstream_deliverables", {}),
                "task_description": invocation_data.get("task_description", ""),
                "delivery_criteria": invocation_data.get("delivery_criteria", {}),
                "task_context": invocation_data.get("task_context", {}),
                "invocation_time": datetime.now().isoformat()
            }
            
            # 更新当前任务
            self.current_task = {
                "id": f"task_{datetime.now().timestamp()}",
                **self.task_input
            }
            
            # 保存到执行历史
            self.context_memory["execution_history"].append({
                "task_id": self.current_task["id"],
                "invocation_data": self.task_input,
                "start_time": datetime.now().isoformat(),
                "status": "started"
            })
            
            # 使用Base Agent进行任务分析和规划
            print(f"🧠 [Skill Agent {self.skill_name}] 使用Base Agent分析任务...")
            task_plan = await self._analyze_task_with_base_agent()
            
            if not task_plan:
                raise Exception("Base Agent未能生成有效任务计划")
            
            # 执行任务
            result = await self._execute_task_plan(task_plan)
            
            # 更新成功率和执行时间
            self._update_task_metrics(success=result.get("success", False))
            
            return result
            
        except Exception as e:
            self.state = AgentState.FAILED
            error_msg = f"任务执行失败: {str(e)}"
            print(f"❌ [Skill Agent {self.skill_name}] {error_msg}")
            
            # 记录失败到历史
            if self.current_task:
                self.context_memory["execution_history"][-1].update({
                    "status": "failed",
                    "error": str(e),
                    "end_time": datetime.now().isoformat()
                })
            
            return {
                "success": False,
                "agent_id": self.agent_id,
                "skill_name": self.skill_name,
                "error": error_msg,
                "context_memory_snapshot": self._get_memory_snapshot()
            }
    
    async def _analyze_task_with_base_agent(self) -> dict:
        """使用Base Agent分析任务并生成执行计划"""
        
        # 构建推理上下文
        reasoning_context = {
            "agent_identity": f"我是{self.skill_name}专家，专注于{self.skill_name}相关任务",
            "current_task": self.task_input,
            "available_skills": self.task_input["skills_list"],
            "upstream_inputs": self.task_input["upstream_deliverables"],
            "delivery_requirements": self.task_input["delivery_criteria"],
            "historical_patterns": self.context_memory["skill_patterns"][-5:],  # 最近5个模式
            "knowledge_snippets": self._get_relevant_knowledge()
        }
        
        # 调用Base Agent进行推理
        task_plan = await self.base_agent.reason_and_plan(
            context=reasoning_context,
            task_description=self.task_input["task_description"]
        )
        
        # 增强任务计划
        enhanced_plan = self._enhance_task_plan(task_plan)
        
        # 保存计划到上下文记忆
        self.context_memory["knowledge_base"][f"plan_{enhanced_plan.get('id', 'unknown')}"] = {
            "plan": enhanced_plan,
            "context": reasoning_context,
            "timestamp": datetime.now().isoformat()
        }
        
        return enhanced_plan
    
    async def _execute_task_plan(self, task_plan: dict) -> dict:
        """执行Base Agent生成的任务计划"""
        
        steps = task_plan.get("steps", [])
        max_steps = len(steps)
        step_idx = 0
        execution_results = {}
        
        while True:
            # 检查是否已完成所有步骤
            if step_idx >= max_steps:
                # 验证交付标准是否满足
                delivery_validation = await self._validate_delivery(
                    execution_results, 
                    self.task_input["delivery_criteria"]
                )
                
                if delivery_validation["meets_criteria"]:
                    self.state = AgentState.COMPLETED
                    print(f"✅ [Skill Agent {self.skill_name}] 任务完成，交付标准验证通过")
                    
                    # 记录成功历史
                    self.context_memory["execution_history"][-1].update({
                        "status": "completed",
                        "end_time": datetime.now().isoformat(),
                        "results": execution_results
                    })
                    
                    # 提取技能模式
                    self._extract_skill_pattern(steps, execution_results)
                    
                    return {
                        "success": True,
                        "agent_id": self.agent_id,
                        "skill_name": self.skill_name,
                        "task_id": self.current_task["id"],
                        "results": execution_results,
                        "checkpoints": self.context_memory["checkpoints"],
                        "delivery_validation": delivery_validation,
                        "memory_snapshot": self._get_memory_snapshot()
                    }
                else:
                    # 交付标准不满足，需要调整或重试
                    print(f"⚠️ [Skill Agent {self.skill_name}] 交付标准不满足，需要调整")
                    
                    # 使用Base Agent重新规划
                    adjustment_plan = await self._plan_adjustment(
                        execution_results, 
                        delivery_validation["issues"]
                    )
                    
                    if adjustment_plan:
                        # 重新执行调整后的计划
                        task_plan = adjustment_plan
                        steps = task_plan.get("steps", [])
                        max_steps = len(steps)
                        step_idx = 0
                        continue
                    else:
                        self.state = AgentState.FAILED
                        return {
                            "success": False,
                            "agent_id": self.agent_id,
                            "skill_name": self.skill_name,
                            "error": "无法满足交付标准",
                            "validation_issues": delivery_validation["issues"]
                        }
            
            # 获取当前步骤
            current_step = steps[step_idx]
            self.current_step = current_step
            self.step_progress = step_idx / max_steps
            
            # 使用Base Agent检查是否需要对齐
            alignment_check = await self.base_agent.check_alignment_needs(
                step=current_step,
                context=self._get_current_context(execution_results)
            )
            
            if alignment_check.get("needs_alignment", False):
                print(f"⏸️ [Skill Agent {self.skill_name}] 步骤{step_idx+1}需要对齐")
                self.task_metrics["alignment_requests"] += 1
                
                # 暂停等待对齐
                alignment_result = await self._pause_for_alignment(
                    step=current_step,
                    alignment_needs=alignment_check.get("reasons", []),
                    execution_context=execution_results
                )
                
                # 处理对齐结果
                step_idx = self._process_alignment_result(
                    alignment_result, 
                    steps, 
                    step_idx, 
                    execution_results
                )
                continue
            
            # 执行当前步骤
            print(f"▶️ [Skill Agent {self.skill_name}] 执行步骤{step_idx+1}/{max_steps}")
            step_result = await self._execute_step(current_step, execution_results)
            
            # 保存结果
            execution_results[f"step_{step_idx}"] = step_result
            
            # 保存检查点
            self._save_checkpoint(step_idx, step_result, execution_results)
            
            # 更新上下文记忆
            self._update_memory_with_step(step_idx, current_step, step_result)
            
            # 移动到下一步
            step_idx += 1
    
    async def _pause_for_alignment(self, step: dict, alignment_needs: list, execution_context: dict) -> dict:
        """暂停执行，等待人类对齐"""
        
        # 构建对齐请求
        alignment_request = {
            "agent_id": self.agent_id,
            "skill_name": self.skill_name,
            "step": step,
            "alignment_needs": alignment_needs,
            "execution_context": execution_context,
            "task_input": self.task_input,
            "current_progress": self.step_progress
        }
        
        # 如果有对齐回调，使用它
        if self.alignment_callback:
            try:
                return await self.alignment_callback(alignment_request)
            except Exception as e:
                print(f"⚠️ 对齐回调失败: {e}")
        
        # 如果没有回调，使用默认对齐机制
        print(f"🔄 [Skill Agent {self.skill_name}] 等待手动对齐...")
        
        # 这里可以实现等待用户输入的逻辑
        # 例如，通过API等待人类输入或设置超时
        
        # 模拟对齐结果
        return {
            "aligned": True,
            "adjusted_step": step,
            "additional_instructions": "",
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_current_context(self, execution_results: dict) -> dict:
        """获取当前执行上下文"""
        return {
            "agent_id": self.agent_id,
            "skill_name": self.skill_name,
            "current_task": self.current_task,
            "execution_results": execution_results,
            "context_memory": self._get_memory_snapshot(),
            "step_progress": self.step_progress
        }
    
    def _get_memory_snapshot(self) -> dict:
        """获取上下文记忆快照"""
        return {
            "history_summary": self.context_memory["execution_history"][-3:],
            "knowledge_keys": list(self.context_memory["knowledge_base"].keys())[-5:],
            "checkpoint_count": len(self.context_memory["checkpoints"]),
            "skill_patterns": self.context_memory["skill_patterns"][-3:]
        }
    
    def _update_task_metrics(self, success: bool):
        """更新任务指标"""
        total_invocations = self.task_metrics["invocations"]
        current_success_rate = self.task_metrics["success_rate"]
        
        # 更新成功率（滑动平均）
        if success:
            new_success_rate = ((current_success_rate * (total_invocations - 1)) + 1) / total_invocations
        else:
            new_success_rate = (current_success_rate * (total_invocations - 1)) / total_invocations
        
        self.task_metrics["success_rate"] = new_success_rate
    
    def _enhance_task_plan(self, plan: dict) -> dict:
        """使用上下文记忆增强任务计划"""
        enhanced_plan = plan.copy()
        
        # 添加从历史中学习的优化
        historical_optimizations = self._get_historical_optimizations()
        if historical_optimizations:
            enhanced_plan["optimizations"] = historical_optimizations
        
        # 添加唯一ID
        enhanced_plan["id"] = f"plan_{datetime.now().timestamp()}_{hash(str(plan))}"
        
        return enhanced_plan
    
    def _extract_skill_pattern(self, steps: list, results: dict):
        """从成功执行中提取技能模式"""
        pattern = {
            "steps_count": len(steps),
            "step_types": [step.get("type", "unknown") for step in steps],
            "successful_approaches": [],
            "timestamp": datetime.now().isoformat(),
            "task_type": self.task_input.get("task_description", "unknown")[:100]
        }
        
        # 添加到模式库（保留最近20个模式）
        self.context_memory["skill_patterns"].append(pattern)
        if len(self.context_memory["skill_patterns"]) > 20:
            self.context_memory["skill_patterns"] = self.context_memory["skill_patterns"][-20:]


class BaseAgent:
    """通用Base Agent，作为Skill Agent的核心推理引擎"""
    
    def __init__(self, agent_id: str, agent_type: str, memory_size: int = 1000):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.memory_size = memory_size
        
        # Base Agent内部状态
        self.reasoning_log = []
    
    async def reason_and_plan(self, context: dict, task_description: str) -> dict:
        """核心推理和规划方法"""
        # 这里可以集成LLM或其他推理引擎
        # 模拟实现
        reasoning_result = {
            "analysis": f"分析任务: {task_description}",
            "steps": self._generate_steps_from_context(context),
            "estimated_difficulty": "medium",
            "potential_risks": [],
            "recommended_approach": "sequential"
        }
        
        # 记录推理日志
        self.reasoning_log.append({
            "timestamp": datetime.now().isoformat(),
            "context_summary": str(context)[:200],
            "reasoning_result": reasoning_result
        })
        
        return reasoning_result
    
    async def check_alignment_needs(self, step: dict, context: dict) -> dict:
        """检查步骤是否需要对齐"""
        # 这里可以实现对齐检查逻辑
        # 模拟实现
        needs_alignment = False
        reasons = []
        
        # 检查是否涉及关键决策
        if step.get("requires_approval", False):
            needs_alignment = True
            reasons.append("步骤需要批准")
        
        # 检查是否有模糊要求
        if "ambiguous" in step.get("description", "").lower():
            needs_alignment = True
            reasons.append("步骤描述模糊")
        
        return {
            "needs_alignment": needs_alignment,
            "reasons": reasons
        }
    
    def _generate_steps_from_context(self, context: dict) -> list:
        """根据上下文生成执行步骤"""
        # 模拟步骤生成
        return [
            {
                "name": "分析输入和要求",
                "type": "analysis",
                "description": "分析上游交付件和任务要求",
                "estimated_time": 5
            },
            {
                "name": "执行核心任务",
                "type": "execution",
                "description": f"执行{context.get('agent_identity', '')}相关任务",
                "estimated_time": 15
            },
            {
                "name": "质量检查",
                "type": "validation",
                "description": "检查结果是否符合交付标准",
                "requires_approval": True
            }
        ]