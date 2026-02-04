import re
from typing import Set

# 正则表达式模式
SINGLE_LINE_IMPORT = re.compile(r'^\s*import\s+(.+)$')
COMMENT_PATTERN = re.compile(r'//.*')


def parse_scala_imports(scala_file: str) -> Set[str]:
    """
    解析Scala文件中的import依赖
    :param scala_file: scala文件路径
    :return: import依赖集合
    """
    imports: Set[str] = set()
    
    with open(scala_file, 'r', encoding='utf-8') as f:
        current_import = None
        
        for line in f:
            line = line.strip()
            
            # 跳过空行
            if not line:
                continue
            
            # 移除行内注释
            if '//' in line:
                line = line[:line.index('//')].strip()
            
            # 如果是import语句的开始或继续
            if line.startswith('import '):
                # 如果有未完成的import，先处理它
                if current_import is not None:
                    process_import(current_import, imports)
                    current_import = None
                
                # 提取import后的内容
                import_content = line[7:]  # 移除"import "
                current_import = import_content
            elif current_import is not None and (line.endswith(',') or line.endswith('{')):
                # 继续累积多行import
                current_import += ' ' + line
            elif current_import is not None:
                # 处理累积的import
                current_import += ' ' + line
                process_import(current_import, imports)
                current_import = None
    
    # 处理最后可能未完成的import
    if current_import is not None:
        process_import(current_import, imports)
    
    return imports


def process_import(import_str: str, imports_set: Set[str]) -> None:
    """处理单个import字符串"""
    # 移除分号
    import_str = import_str.rstrip(';').strip()
    
    # 如果没有花括号，直接添加
    if '{' not in import_str:
        imports_set.add(import_str.strip())
        return
    
    # 处理带花括号的import
    parts = split_import_with_braces(import_str)
    for part in parts:
        if part and part != '_':
            imports_set.add(part.strip())


def split_import_with_braces(import_str: str) -> Set[str]:
    """拆分带花括号的import语句"""
    results = set()
    
    # 分割多个import（逗号分隔）
    import_items = split_import_items(import_str)
    
    for item in import_items:
        if '{' not in item:
            results.add(item)
            continue
        
        # 处理花括号
        prefix, brace_content = item.split('{', 1)
        prefix = prefix.rstrip('.').strip()
        brace_content = brace_content.rstrip('}').strip()
        
        # 拆分花括号内的内容
        for inner_item in brace_content.split(','):
            inner_item = inner_item.strip()
            if not inner_item or inner_item == '_':
                continue
            
            # 处理重命名
            if '=>' in inner_item:
                original = inner_item.split('=>')[0].strip()
                inner_item = original
            
            results.add(f"{prefix}.{inner_item}")
    
    return results


def split_import_items(import_str: str) -> list:
    """拆分逗号分隔的import项"""
    items = []
    current = []
    brace_depth = 0
    
    for char in import_str:
        if char == '{':
            brace_depth += 1
            current.append(char)
        elif char == '}':
            brace_depth -= 1
            current.append(char)
        elif char == ',' and brace_depth == 0:
            items.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    
    if current:
        items.append(''.join(current).strip())
    
    return items


if __name__ == "__main__":
    scala_path = "example.scala"  # 修改为您的Scala文件名
    
    try:
        deps = parse_scala_imports(scala_path)
        
        print("解析到的import依赖:")
        print("=" * 60)
        for d in sorted(deps):
            print(d)
        
        print(f"\n总计: {len(deps)} 个import项")
        
    except FileNotFoundError:
        print(f"错误: 文件 {scala_path} 未找到")
        print("请确保Scala文件在当前目录下")
    except Exception as e:
        print(f"解析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()