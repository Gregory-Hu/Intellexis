# src/server.py
from fastapi import FastAPI
from system.engineering_system import EngineeringSystem

app = FastAPI()

# 🌍 世界只建一次
system = EngineeringSystem("config/system_config.json")
system.build()

@app.post("/run")
def run_task(request: dict):
    runtime = system.create_runtime()
    return runtime.run(request["user_request"])
