# workbench/core/workflow/step_registry.py
"""
步骤注册表 - 基础设施（重构版）
"""

from __future__ import annotations

from typing import Dict, Any, List, Type, Optional
from dataclasses import dataclass
import threading
import inspect
import importlib.util
from pathlib import Path
import logging

from .step_base import BaseStep, StepConfig

logger = logging.getLogger(__name__)


# =========================
# 内部数据结构
# =========================

@dataclass(frozen=True)
class StepEntry:
    """步骤注册条目"""
    step_id: str
    step_class: Type[BaseStep]
    config: StepConfig
    metadata: Dict[str, Any]


# =========================
# StepRegistry
# =========================

class StepRegistry:
    """步骤注册表（线程安全单例）"""

    _instance: Optional["StepRegistry"] = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
            return cls._instance

    # ---------------------
    # 初始化
    # ---------------------

    def _initialize(self):
        self._registry: Dict[str, StepEntry] = {}
        self._lock = threading.RLock()

    # ---------------------
    # 注册相关
    # ---------------------

    def register(self, step_class: Type[BaseStep], config: StepConfig) -> str:
        """注册一个步骤类，返回 step_id"""

        if not inspect.isclass(step_class):
            raise TypeError("step_class must be a class")

        if not issubclass(step_class, BaseStep):
            raise TypeError("step_class must inherit from BaseStep")

        if not isinstance(config, StepConfig):
            raise TypeError("config must be StepConfig")

        step_id = f"{step_class.__module__}.{step_class.__name__}"

        metadata = self._build_metadata(config)

        entry = StepEntry(
            step_id=step_id,
            step_class=step_class,
            config=config,
            metadata=metadata,
        )

        with self._lock:
            if step_id in self._registry:
                logger.warning("Step %s is already registered, overriding", step_id)
            self._registry[step_id] = entry

        logger.debug("Registered step: %s", step_id)
        return step_id

    def unregister(self, step_id: str) -> bool:
        """取消注册步骤"""
        with self._lock:
            return self._registry.pop(step_id, None) is not None

    def clear(self):
        """清空注册表（常用于测试）"""
        with self._lock:
            self._registry.clear()

    # ---------------------
    # Discover
    # ---------------------

    def discover_steps(self, directory: str | Path):
        """
        从目录中发现并注册步骤（基于文件路径 import）
        """
        steps_dir = Path(directory).resolve()
        if not steps_dir.exists():
            raise FileNotFoundError(steps_dir)

        for py_file in steps_dir.rglob("*.py"):
            if py_file.name.startswith("_") or py_file.name.startswith("test_"):
                continue

            try:
                self._load_module_from_file(py_file)
            except Exception:
                logger.exception("Failed to discover steps in %s", py_file)

    def _load_module_from_file(self, py_file: Path):
        module_name = f"_step_{py_file.stem}_{hash(py_file)}"

        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {py_file}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseStep)
                and obj is not BaseStep
                and hasattr(obj, "config")
            ):
                self.register(obj, obj.config)

    # ---------------------
    # 查询
    # ---------------------

    def get_step_class(self, step_id: str) -> Optional[Type[BaseStep]]:
        with self._lock:
            entry = self._registry.get(step_id)
            return entry.step_class if entry else None

    def get_entry(self, step_id: str) -> Optional[StepEntry]:
        with self._lock:
            return self._registry.get(step_id)

    def list_steps(self) -> List[StepEntry]:
        with self._lock:
            return list(self._registry.values())

    # ---------------------
    # 教学 & 搜索
    # ---------------------

    def get_teaching_catalog(self) -> List[Dict[str, Any]]:
        """获取教学步骤目录（不裁剪内容）"""
        with self._lock:
            catalog = [
                {
                    "id": entry.step_id,
                    **entry.metadata,
                    "description": entry.config.description,
                }
                for entry in self._registry.values()
            ]

        catalog.sort(
            key=lambda x: (
                x.get("type"),
                x.get("difficulty"),
                x.get("name"),
            )
        )
        return catalog

    def find_steps_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {"id": entry.step_id, **entry.metadata}
                for entry in self._registry.values()
                if tag in entry.metadata.get("tags", [])
            ]

    # ---------------------
    # 实例化
    # ---------------------

    def create_step_instance(self, step_id: str, **kwargs) -> Optional[BaseStep]:
        entry = self.get_entry(step_id)
        if not entry:
            return None

        step = entry.step_class(**kwargs)

        # 可选：统一生命周期钩子
        if hasattr(step, "validate"):
            step.validate()

        return step

    # ---------------------
    # 内部工具
    # ---------------------

    @staticmethod
    def _build_metadata(config: StepConfig) -> Dict[str, Any]:
        teaching_points = []
        for tp in (config.teaching_points or []):
            teaching_points.append(
                {
                    "concept": tp.concept,
                    "explanation": tp.explanation,
                }
            )

        return {
            "name": config.name,
            "description": config.description,
            "type": config.step_type.value,
            "author": config.author,
            "tags": list(config.tags or []),
            "difficulty": config.difficulty,
            "version": config.version,
            "teaching_points": teaching_points,
        }


# =========================
# 全局实例
# =========================

registry = StepRegistry()
