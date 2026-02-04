#!/usr/bin/env python3
"""
最简单的Chisel模块查找器
"""

import sys
import os

def find_modules(file_path):
    """查找定义了val io的类"""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    modules = []
    in_module = False
    class_name = ""
    found_io = False
    brace_count = 0
    
    for line in lines:
        # 查找类定义
        if 'class ' in line and 'extends' in line and 'Module' in line:
            # 提取类名
            start = line.find('class ') + 6
            end = min(
                line.find('(', start) if '(' in line else len(line),
                line.find(':', start) if ':' in line else len(line),
                line.find(' ', start + 1) if ' ' in line[start:] else len(line),
                line.find('\n', start) if '\n' in line else len(line)
            )
            class_name = line[start:end].strip()
            in_module = True
            brace_count = 0
            found_io = False
        
        if in_module:
            # 检查是否定义了val io
            if 'val io' in line and '=' in line:
                found_io = True
            
            # 统计大括号
            brace_count += line.count('{')
            brace_count -= line.count('}')
            
            # 类定义结束
            if brace_count == 0 and line.strip().endswith('}'):
                if found_io:
                    modules.append(class_name)
                in_module = False
                class_name = ""
                found_io = False
    
    return modules

def main():
    if len(sys.argv) != 2:
        print("用法: python simple_finder.py <Scala文件>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        # 创建示例文件
        with open(file_path, 'w') as f:
            f.write("""
import chisel3._

class MyModule extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt(8.W))
    val out = Output(UInt(8.W))
  })
  io.out := io.in
}

class AnotherModule extends Module {
  val io = IO(new Bundle {
    val enable = Input(Bool())
    val data = Output(UInt(16.W))
  })
  io.data := 0.U
}
""")
        print(f"已创建示例文件: {file_path}")
    
    modules = find_modules(file_path)
    
    if modules:
        print(f"找到 {len(modules)} 个Chisel模块:")
        for module in modules:
            print(f"  - {module}")
    else:
        print("没有找到Chisel模块")
        print("\n请确保文件包含类似这样的代码:")
        print("""
class ModuleName extends Module {
  val io = IO(new Bundle {
    // 端口定义
  })
}
""")

if __name__ == '__main__':
    main()