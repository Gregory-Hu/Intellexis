下面是一份可直接放进仓库的《架构设计文档（Architecture Design Doc）》，内容严格对齐你前面校正过的架构理念，并且完全匹配你现在的目录结构。
我会用工程文档风格来写，而不是概念性说明，方便你后续对内评审、对外沟通或继续演进。

工程智能体系统架构设计文档（MVP）
1. 设计目标

本系统旨在构建一个以工程世界模型为核心、以 SOP Skill 为约束的多层智能体系统，用于在工程场景（如 EDA、代码工程）中，实现：

从人类需求到工程任务的结构化转化

受控、可审计的工程动作执行

可演进的智能体体系（从 MVP 到规模化系统）

MVP 阶段核心目标

保留正确的架构分层

最小化功能复杂度

实现一个可运行、可演示的闭环系统

2. 总体架构概览

系统采用自底向上分层架构，层与层之间存在严格的单向依赖关系。

┌──────────────────────────────┐
│        需求智能体（Agent）     │  ← 面向用户
└──────────────▲───────────────┘
               │
┌──────────────┴───────────────┐
│        任务智能体（Agent）     │  ← 任务执行
└──────────────▲───────────────┘
               │
┌──────────────┴───────────────┐
│      工程世界建模智能体        │  ← 建模/感知
└──────────────▲───────────────┘
               │
┌──────────────┴───────────────┐
│ SOP Skill 库 & 工程世界模型    │  ← 系统地基
└──────────────────────────────┘

架构基本原则

工程世界模型（World Model）是唯一事实源

所有工程行为必须通过 Skill 执行

智能体不直接修改世界，只通过 Skill 间接作用

上层只依赖下层，不允许反向调用

3. 代码目录结构说明
```
src/
├── agents/                # 各类智能体（策略 / 推理）
│   ├── modeling/
│   ├── task/
│   └── requirement/
│
├── world_model/           # 工程世界模型（纯数据 + schema）
│   └── world.py
│
├── lib/
│   ├── sops/
│   └── skills/
│
├── system/                # 系统内核（长期存在）
│   ├── engineering_system.py
│   └── __init__.py
│
├── runtime/               # 运行时（会话 / 一次执行）
│   ├── engineering_runtime.py
│   └── __init__.py
│
└── app.py / cli.py / api.py
```

4. 各层详细设计
4.1 world_model —— 工程世界模型层（Layer 0）
职责

描述工程系统的当前状态与结构

作为系统中所有智能体和 Skill 的共享上下文

提供唯一、可追溯的事实来源

设计原则

❌ 不包含推理逻辑

❌ 不调用 Skill

❌ 不感知智能体

✅ 只存储结构化数据

示例结构
class EngineeringWorld:
    def __init__(self):
        self.modules = {}
        self.files = {}
        self.simulation_status = None
        self.history = []

4.2 lib/skills —— Skill 层（Layer 0）
职责

Skill 是系统中唯一允许对工程世界产生副作用的单元，封装：

工程工具调用（如 EDA、编译、仿真）

代码修改

文档生成

EDA 工具的使用本质上是一个 Skill

Skill 抽象接口
class Skill:
    name: str

    def run(self, world: EngineeringWorld, params: dict):
        raise NotImplementedError

设计原则

Skill 是 确定性的

Skill 的输入 / 输出 结构化

Skill 不做决策，只做动作

4.3 lib/sops —— SOP 层（Layer 0）
职责

定义标准工程流程

描述 Skill 的组合方式

作为智能体规划和执行的参考模板

MVP 阶段策略

SOP 可先以 Python / YAML 静态定义

不做动态编排引擎

示例（概念）
name: add_feature_and_verify
steps:
  - modify_code
  - run_simulation
  - generate_report

4.4 agents/modeling_agent —— 工程世界建模智能体（Layer 1）
职责

通过调用 Skill，将外部工程对象（代码、文件、工具输出）
映射为工程世界模型中的结构化实体

维护工程世界模型的一致性

特点

❌ 不接收用户需求

❌ 不决定任务目标

✅ 专注“工程事实建模”

示例行为
class ModelingAgent:
    def build_world(self, world):
        self.skills["parse_code"].run(world, {})

4.5 agents/task_agent —— 任务智能体（Layer 2）
职责

接收已拆解好的任务列表

顺序（或未来并行）执行任务

调用对应 Skill 并更新世界模型

特点

不理解业务语义

不修改任务计划

是一个受控执行器

class TaskAgent:
    def execute(self, world, tasks):
        for task in tasks:
            self.skills[task["skill"]].run(world, task.get("params", {}))

4.6 agents/requirement_agent —— 需求智能体（Layer 3）
职责

系统中唯一直接与用户交互的智能体

将自然语言需求转换为结构化任务或 SOP

LLM 使用边界

LLM 只允许存在于该层

仅用于：

需求理解

任务拆解

结果解释

MVP 实现策略

强模板

少场景

输出固定 JSON 结构

4.7 runtime —— 运行时与调度层
职责

组织智能体调用顺序

管理一次完整执行流程的生命周期

提供统一入口（CLI / API）

MVP 特点

单进程

顺序执行

无并发、无调度策略

world = EngineeringWorld()
modeling_agent.build_world(world)
tasks = requirement_agent.analyze(user_input)
task_agent.execute(world, tasks)

5. 系统执行主流程（MVP）
用户需求
  ↓
需求智能体（解析/拆解）
  ↓
任务智能体（执行任务）
  ↓
Skill（工程动作）
  ↓
工程世界模型（状态更新）
  ↓
结果输出（文档 / 状态）

6. 架构可演进性说明

该 MVP 架构支持以下自然演进方向：

World Model：从内存对象 → 图模型

SOP：从静态定义 → 可编排流程

Runtime：从顺序执行 → DAG / Temporal

Agent：从单实例 → 多实例协作

无需推翻现有分层。

7. 总结

本架构的核心价值在于：

把“智能”限制在该限制的地方，把“工程事实”和“工程动作”变成稳定资产。

即使在 MVP 阶段，也坚持正确的层次和因果关系，为后续规模化演进奠定基础。