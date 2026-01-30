
架构图

graph TB
    subgraph "Human Engineer Interface Layer"
        UI[Web UI / CLI / IDE Plugin]
        Editor[Workflow Editor]
        Inspector[State Inspector]
        Dashboard[Dashboard]
    end
    
    subgraph "Core Workbench Engine"
        WB[Workbench Engine]
        IE[Incremental Executor]
        SM[Snapshot Manager]
        CP[Checkpoint Manager]
        DR[Dependency Resolver]
    end
    
    subgraph "State Management Layer"
        SS[State Storage]
        Cache[Result Cache]
        Snapshots[Versioned Snapshots]
        Checkpoints[User Checkpoints]
    end
    
    subgraph "Chisel3 Specialized Layer"
        Parser[Chisel3 Parser]
        Analyzer[AST Analyzer]
        Generator[Code Generator]
        Verifier[Verilog Verifier]
    end
    
    subgraph "Workflow Components"
        Steps[Step Registry]
        LLM[LLM Integration]
        Validators[Validation Engine]
        Batch[Batch Executor]
    end
    
    subgraph "External Systems"
        Git[Git Repository]
        Chisel[Chisel3 Project]
        LLM_API[DeepSeek API]
        CI_CD[CI/CD Pipeline]
    end
    
    UI --> WB
    Editor --> Steps
    Inspector --> SS
    
    WB --> IE
    WB --> SM
    WB --> CP
    WB --> DR
    
    IE --> SS
    SM --> Snapshots
    CP --> Checkpoints
    
    WB --> Parser
    Parser --> Analyzer
    Analyzer --> Generator
    Generator --> Verifier
    
    Steps --> LLM
    Steps --> Validators
    Steps --> Batch
    
    Parser --> Chisel
    Generator --> Chisel
    LLM --> LLM_API
    Batch --> CI_CD
    SS --> Git

    描述
    个专为芯片设计工程师打造的“AI教学与协作工作台”原型（V1.0）。它让专家能通过可视化流程，像培训新员工一样，一步步教AI理解复杂的处理器IP代码、执行验证任务。目标是将专家的隐性知识转化为可重复、可扩展的标准化操作流程，为未来AI自动化奠定基础。

    已完成任务


    当前任务
    | 周四晚  | `BaseStep / StepResult / StepRegistry` | Step ABI          |

    | 周一晚  | 项目初始化，目录结构（按新分层）                       | pyproject.toml，骨架 |done|
| 周二晚  | `state_models.py`（不可变 / 可变区分）          | 核心状态模型            |done|
| 周三晚  | `WorkbenchContext` + `workbench.py` 框架 | 中枢调度骨架            | done |