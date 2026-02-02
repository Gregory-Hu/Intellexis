# src/main.py

from system.engineering_system import EngineeringSystem
from interface.interactive_session import InteractiveSession

def main():
    # ① 系统启动
    system = EngineeringSystem("config/system_config.json")
    system.build()

    # ② 创建一次运行时
    runtime = system.create_runtime()

    # ③ 🔥 拉起调试 chat
    session = InteractiveSession(runtime)
    session.chat()

if __name__ == "__main__":
    main()
