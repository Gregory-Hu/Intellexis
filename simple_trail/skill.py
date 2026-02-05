import re
from pathlib import Path


def compile_skill(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8")

    def section(name):
        pattern = rf"## {name}\n(.*?)(?=\n## |\Z)"
        m = re.search(pattern, text, re.S)
        return m.group(1).strip() if m else ""

    skill = {
        "role": section("Role"),
        "phase": section("Phase"),
        "rules": [l.strip("- ").strip() for l in section("Rules").splitlines() if l],
        "decisions": [l.strip("- ").strip() for l in section("Decisions").splitlines() if l],
        "confidence_threshold": 0.9,
    }

    return skill

if __name__ == "__main__":
    skill_data = compile_skill("interface_traverse.md")
    for key, value in skill_data.items():
        print(f"{key}: {value}\n")
