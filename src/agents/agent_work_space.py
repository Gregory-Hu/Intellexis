import logging
import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Any
from pathlib import Path
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FileType(Enum):
    """文件类型枚举"""
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    UNKNOWN = "unknown"

@dataclass
class FileInfo:
    """文件信息类"""
    name: str
    path: str
    type: FileType
    size: int = 0
    modified: float = 0
    created: float = 0
    extension: str = ""
    is_hidden: bool = False
    
    @classmethod
    def from_path(cls, path: Union[str, Path]) -> "FileInfo":
        """从路径创建FileInfo"""
        path_obj = Path(path)
        stat_info = path_obj.stat()
        
        # 判断文件类型
        if path_obj.is_file():
            file_type = FileType.FILE
        elif path_obj.is_dir():
            file_type = FileType.DIRECTORY
        elif path_obj.is_symlink():
            file_type = FileType.SYMLINK
        else:
            file_type = FileType.UNKNOWN
        
        # 获取扩展名
        extension = path_obj.suffix.lower()
        if extension.startswith('.'):
            extension = extension[1:]
        
        return cls(
            name=path_obj.name,
            path=str(path_obj),
            type=file_type,
            size=stat_info.st_size if file_type == FileType.FILE else 0,
            modified=stat_info.st_mtime,
            created=stat_info.st_ctime,
            extension=extension,
            is_hidden=path_obj.name.startswith('.')
        )

@dataclass
class DirectoryStructure:
    """目录结构类"""
    root_path: str
    structure: Dict[str, Any]
    total_dirs: int = 0
    total_files: int = 0
    total_size: int = 0
    scan_time: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "root_path": self.root_path,
            "structure": self.structure,
            "statistics": {
                "total_dirs": self.total_dirs,
                "total_files": self.total_files,
                "total_size": self.total_size
            },
            "scan_time": self.scan_time.isoformat()
        }


class FileSystemTool:
    """文件系统工具类"""
    
    def __init__(self):
        self.supported_extensions = {
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg'],
            'documents': ['.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'],
            'code': ['.py', '.js', '.java', '.cpp', '.c', '.h', '.html', '.css', '.json', '.xml'],
            'data': ['.csv', '.tsv', '.jsonl', '.parquet', '.feather']
        }
    
    def get_file_structure(
        self, 
        directory: str, 
        max_depth: Optional[int] = None,
        include_hidden: bool = False,
        exclude_patterns: Optional[List[str]] = None
    ) -> DirectoryStructure:
        """
        获取指定目录的文件结构
        
        参数:
            directory: 目录路径
            max_depth: 最大遍历深度，None表示无限制
            include_hidden: 是否包含隐藏文件/目录
            exclude_patterns: 要排除的文件/目录模式列表
            
        返回:
            DirectoryStructure对象
        """
        exclude_patterns = exclude_patterns or []
        
        def _should_exclude(name: str) -> bool:
            """检查是否应该排除该文件/目录"""
            for pattern in exclude_patterns:
                if pattern in name:
                    return True
            return False
        
        def _scan_dir(current_path: Path, current_depth: int = 0) -> Dict[str, Any]:
            """递归扫描目录"""
            if max_depth is not None and current_depth > max_depth:
                return {}
            
            try:
                items = list(current_path.iterdir())
            except (PermissionError, OSError) as e:
                logger.warning(f"无法访问目录 {current_path}: {e}")
                return {
                    "name": current_path.name,
                    "path": str(current_path),
                    "type": "directory",
                    "error": str(e),
                    "children": []
                }
            
            dir_info = {
                "name": current_path.name,
                "path": str(current_path),
                "type": "directory",
                "children": [],
                "file_count": 0,
                "dir_count": 0,
                "total_size": 0
            }
            
            for item in items:
                # 跳过隐藏文件/目录（如果设置）
                if not include_hidden and item.name.startswith('.'):
                    continue
                    
                # 跳过排除模式匹配的文件/目录
                if _should_exclude(item.name):
                    continue
                
                try:
                    if item.is_dir():
                        # 递归处理子目录
                        child_structure = _scan_dir(item, current_depth + 1)
                        if child_structure:
                            dir_info["children"].append(child_structure)
                            dir_info["dir_count"] += 1
                    else:
                        # 添加文件
                        file_info = FileInfo.from_path(item)
                        dir_info["children"].append({
                            "name": file_info.name,
                            "path": file_info.path,
                            "type": "file",
                            "size": file_info.size,
                            "modified": file_info.modified,
                            "extension": file_info.extension,
                            "is_hidden": file_info.is_hidden
                        })
                        dir_info["file_count"] += 1
                        dir_info["total_size"] += file_info.size
                except (PermissionError, OSError) as e:
                    logger.warning(f"无法访问 {item}: {e}")
                    continue
            
            # 对子项排序：目录在前，文件在后，按名称排序
            dir_info["children"].sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
            
            return dir_info
        
        directory_path = Path(directory).expanduser().resolve()
        
        if not directory_path.exists():
            raise FileNotFoundError(f"目录不存在: {directory}")
        
        if not directory_path.is_dir():
            raise NotADirectoryError(f"路径不是目录: {directory}")
        
        structure = _scan_dir(directory_path)
        
        # 计算统计信息
        def _calculate_stats(struct: Dict) -> tuple:
            dirs = 1 if struct["type"] == "directory" else 0
            files = 0 if struct["type"] == "directory" else 1
            total_size = struct.get("total_size", 0) if struct["type"] == "directory" else struct.get("size", 0)
            
            if "children" in struct:
                for child in struct["children"]:
                    child_dirs, child_files, child_size = _calculate_stats(child)
                    dirs += child_dirs
                    files += child_files
                    total_size += child_size
            
            return dirs, files, total_size
        
        total_dirs, total_files, total_size = _calculate_stats(structure)
        
        return DirectoryStructure(
            root_path=str(directory_path),
            structure=structure,
            total_dirs=total_dirs,
            total_files=total_files,
            total_size=total_size
        )
    
    def print_tree(self, structure: DirectoryStructure, show_size: bool = False, show_details: bool = False):
        """以树状格式打印文件结构"""
        
        def _print_node(node: Dict, indent: str = "", last: bool = True, depth: int = 0):
            """递归打印节点"""
            # 当前项的显示
            icon = "📁" if node["type"] == "directory" else "📄"
            prefix = "└── " if last else "├── "
            
            if node["type"] == "directory":
                line = f"{indent}{prefix}{icon} {node['name']}/"
                if show_details:
                    file_count = node.get("file_count", 0)
                    dir_count = node.get("dir_count", 0)
                    size = node.get("total_size", 0)
                    line += f" [{dir_count} dirs, {file_count} files"
                    if show_size:
                        line += f", {self._format_size(size)}"
                    line += "]"
                print(line)
            else:
                line = f"{indent}{prefix}{icon} {node['name']}"
                if show_details:
                    size = node.get("size", 0)
                    modified = datetime.fromtimestamp(node.get("modified", 0)).strftime("%Y-%m-%d %H:%M")
                    line += f" [{self._format_size(size)}, {modified}]"
                elif show_size:
                    size = node.get("size", 0)
                    line += f" ({self._format_size(size)})"
                print(line)
            
            # 如果是目录且有子项，递归打印子项
            if node["type"] == "directory" and "children" in node:
                children = node["children"]
                for i, child in enumerate(children):
                    is_last = i == len(children) - 1
                    child_indent = indent + ("    " if last else "│   ")
                    _print_node(child, child_indent, is_last, depth + 1)
        
        print(f"目录结构: {structure.root_path}")
        print(f"扫描时间: {structure.scan_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        _print_node(structure.structure)
        
        print(f"\n统计:")
        print(f"  目录数量: {structure.total_dirs}")
        print(f"  文件数量: {structure.total_files}")
        print(f"  总大小: {self._format_size(structure.total_size)}")
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    def find_files(self, directory: str, pattern: str, recursive: bool = True) -> List[str]:
        """查找文件"""
        import fnmatch
        
        matches = []
        directory_path = Path(directory).expanduser().resolve()
        
        if recursive:
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    if fnmatch.fnmatch(file, pattern):
                        matches.append(str(Path(root) / file))
        else:
            for item in directory_path.iterdir():
                if item.is_file() and fnmatch.fnmatch(item.name, pattern):
                    matches.append(str(item))
        
        return sorted(matches)
    
    def get_file_type_summary(self, directory: str) -> Dict[str, int]:
        """获取文件类型统计"""
        summary = {}
        directory_path = Path(directory).expanduser().resolve()
        
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                path = Path(root) / file
                file_info = FileInfo.from_path(path)
                
                # 根据扩展名分类
                category = "other"
                for cat, exts in self.supported_extensions.items():
                    if file_info.extension in [ext[1:] if ext.startswith('.') else ext for ext in exts]:
                        category = cat
                        break
                
                summary[category] = summary.get(category, 0) + 1
        
        return summary    