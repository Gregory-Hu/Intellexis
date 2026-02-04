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

class SkillAgent:
    """SkillAgent 类，每个实例有自己的工作目录"""
    
    def __init__(self, agent_id: str, base_workspace: Optional[str] = None):
        """
        初始化 SkillAgent
        
        参数:
            agent_id: 代理的唯一标识符
            base_workspace: 工作空间的根目录，如果为None则使用临时目录
        """
        self.agent_id = agent_id
        self.fs_tool = FileSystemTool()
        
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
    
    def cd(self, directory: str) -> bool:
        """
        切换工作目录
        
        参数:
            directory: 目标目录，可以是相对路径或绝对路径
            
        返回:
            是否切换成功
        """
        try:
            # 解析路径
            if Path(directory).is_absolute():
                new_path = Path(directory)
            else:
                new_path = self.work_directory / directory
            
            # 规范化路径
            new_path = new_path.resolve()
            
            # 检查路径是否存在且是目录
            if not new_path.exists():
                logger.error(f"目录不存在: {new_path}")
                return False
            
            if not new_path.is_dir():
                logger.error(f"路径不是目录: {new_path}")
                return False
            
            # 确保新目录在工作空间内（安全限制）
            try:
                new_path.relative_to(self.base_workspace)
            except ValueError:
                logger.error(f"目录不在工作空间内: {new_path}")
                return False
            
            self.work_directory = new_path
            logger.info(f"工作目录已切换到: {self.work_directory}")
            return True
            
        except Exception as e:
            logger.error(f"切换目录失败: {e}")
            return False
    
    def pwd(self) -> str:
        """获取当前工作目录"""
        return str(self.work_directory)
    
    def ls(self, path: Optional[str] = None, detailed: bool = False) -> List[Dict]:
        """
        列出目录内容
        
        参数:
            path: 要列出的目录路径，None表示当前目录
            detailed: 是否显示详细信息
            
        返回:
            目录内容列表
        """
        target_dir = self.work_directory if path is None else Path(path)
        if not target_dir.is_absolute():
            target_dir = self.work_directory / target_dir
        
        target_dir = target_dir.expanduser().resolve()
        
        if not target_dir.exists():
            logger.error(f"目录不存在: {target_dir}")
            return []
        
        if not target_dir.is_dir():
            logger.error(f"路径不是目录: {target_dir}")
            return []
        
        items = []
        for item in sorted(target_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            file_info = FileInfo.from_path(item)
            
            if detailed:
                items.append({
                    "name": file_info.name,
                    "type": file_info.type.value,
                    "size": file_info.size,
                    "modified": datetime.fromtimestamp(file_info.modified).strftime("%Y-%m-%d %H:%M"),
                    "is_hidden": file_info.is_hidden
                })
            else:
                items.append({
                    "name": file_info.name,
                    "type": file_info.type.value,
                    "is_hidden": file_info.is_hidden
                })
        
        return items
    
    def mkdir(self, directory: str, parents: bool = True) -> bool:
        """
        创建目录
        
        参数:
            directory: 目录路径
            parents: 是否创建父目录
            
        返回:
            是否创建成功
        """
        try:
            if Path(directory).is_absolute():
                target_dir = Path(directory)
            else:
                target_dir = self.work_directory / directory
            
            # 确保目录在工作空间内
            try:
                target_dir.resolve().relative_to(self.base_workspace)
            except ValueError:
                logger.error(f"目录不在工作空间内: {target_dir}")
                return False
            
            target_dir.mkdir(parents=parents, exist_ok=True)
            logger.info(f"目录已创建: {target_dir}")
            return True
            
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            return False
    
    def rm(self, path: str, recursive: bool = False) -> bool:
        """
        删除文件或目录
        
        参数:
            path: 路径
            recursive: 是否递归删除目录
            
        返回:
            是否删除成功
        """
        try:
            if Path(path).is_absolute():
                target_path = Path(path)
            else:
                target_path = self.work_directory / path
            
            target_path = target_path.expanduser().resolve()
            
            # 确保路径在工作空间内
            try:
                target_path.relative_to(self.base_workspace)
            except ValueError:
                logger.error(f"路径不在工作空间内: {target_path}")
                return False
            
            if not target_path.exists():
                logger.error(f"路径不存在: {target_path}")
                return False
            
            if target_path.is_file() or target_path.is_symlink():
                target_path.unlink()
                logger.info(f"文件已删除: {target_path}")
            elif target_path.is_dir():
                if recursive:
                    shutil.rmtree(target_path)
                    logger.info(f"目录已递归删除: {target_path}")
                else:
                    target_path.rmdir()
                    logger.info(f"目录已删除: {target_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return False
    
    def cp(self, source: str, destination: str, recursive: bool = False) -> bool:
        """
        复制文件或目录
        
        参数:
            source: 源路径
            destination: 目标路径
            recursive: 是否递归复制目录
            
        返回:
            是否复制成功
        """
        try:
            # 解析源路径
            if Path(source).is_absolute():
                src_path = Path(source)
            else:
                src_path = self.work_directory / source
            
            src_path = src_path.expanduser().resolve()
            
            # 解析目标路径
            if Path(destination).is_absolute():
                dst_path = Path(destination)
            else:
                dst_path = self.work_directory / destination
            
            dst_path = dst_path.expanduser().resolve()
            
            # 确保路径在工作空间内
            try:
                src_path.relative_to(self.base_workspace)
                dst_path.relative_to(self.base_workspace)
            except ValueError:
                logger.error(f"路径不在工作空间内")
                return False
            
            if not src_path.exists():
                logger.error(f"源路径不存在: {src_path}")
                return False
            
            if src_path.is_file():
                shutil.copy2(src_path, dst_path)
                logger.info(f"文件已复制: {src_path} -> {dst_path}")
            elif src_path.is_dir():
                if recursive:
                    if dst_path.exists():
                        # 如果目标已存在，复制到目标目录内
                        shutil.copytree(src_path, dst_path / src_path.name, dirs_exist_ok=True)
                    else:
                        shutil.copytree(src_path, dst_path)
                    logger.info(f"目录已递归复制: {src_path} -> {dst_path}")
                else:
                    logger.error(f"源路径是目录，但未设置recursive=True")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"复制失败: {e}")
            return False
    
    def get_structure(self, **kwargs) -> DirectoryStructure:
        """
        获取当前工作目录的文件结构
        
        参数:
            **kwargs: 传递给FileSystemTool.get_file_structure的参数
            
        返回:
            DirectoryStructure对象
        """
        return self.fs_tool.get_file_structure(str(self.work_directory), **kwargs)
    
    def print_structure(self, **kwargs):
        """打印当前工作目录的文件结构"""
        structure = self.get_structure(**kwargs)
        self.fs_tool.print_tree(structure, **kwargs)
    
    def find(self, pattern: str, recursive: bool = True) -> List[str]:
        """
        在当前工作目录查找文件
        
        参数:
            pattern: 文件名模式（支持通配符）
            recursive: 是否递归查找
            
        返回:
            匹配的文件路径列表
        """
        return self.fs_tool.find_files(str(self.work_directory), pattern, recursive)
    
    def create_file(self, filename: str, content: str = "", overwrite: bool = False) -> bool:
        """
        创建文件
        
        参数:
            filename: 文件名
            content: 文件内容
            overwrite: 是否覆盖已存在的文件
            
        返回:
            是否创建成功
        """
        try:
            file_path = self.work_directory / filename
            
            if file_path.exists() and not overwrite:
                logger.error(f"文件已存在: {file_path}")
                return False
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"文件已创建: {file_path} (大小: {len(content)} 字节)")
            return True
            
        except Exception as e:
            logger.error(f"创建文件失败: {e}")
            return False
    
    def read_file(self, filename: str) -> Optional[str]:
        """
        读取文件内容
        
        参数:
            filename: 文件名
            
        返回:
            文件内容，如果失败则返回None
        """
        try:
            file_path = self.work_directory / filename
            
            if not file_path.exists():
                logger.error(f"文件不存在: {file_path}")
                return None
            
            if not file_path.is_file():
                logger.error(f"路径不是文件: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return content
            
        except Exception as e:
            logger.error(f"读取文件失败: {e}")
            return None
    
    def get_info(self) -> Dict[str, Any]:
        """获取代理信息"""
        # 计算工作目录使用情况
        total_size = 0
        file_count = 0
        dir_count = 0
        
        for root, dirs, files in os.walk(self.work_directory):
            dir_count += len(dirs)
            file_count += len(files)
            for file in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, file))
                except OSError:
                    pass
        
        return {
            "agent_id": self.agent_id,
            "work_directory": str(self.work_directory),
            "base_workspace": str(self.base_workspace),
            "usage": {
                "total_size": total_size,
                "formatted_size": self.fs_tool._format_size(total_size),
                "file_count": file_count,
                "directory_count": dir_count
            },
            "directories": {
                "logs": str(self.log_directory),
                "data": str(self.data_directory),
                "cache": str(self.cache_directory)
            }
        }

class SkillAgentManager:
    """SkillAgent管理器，用于管理多个SkillAgent实例"""
    
    def __init__(self, workspace_root: Optional[str] = None):
        """
        初始化管理器
        
        参数:
            workspace_root: 工作空间根目录
        """
        if workspace_root:
            self.workspace_root = Path(workspace_root).expanduser().resolve()
        else:
            self.workspace_root = Path(tempfile.gettempdir()) / "skill_agents"
        
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.agents: Dict[str, SkillAgent] = {}
        
        # 加载已存在的代理
        self._load_existing_agents()
        
        logger.info(f"SkillAgent管理器初始化完成，工作空间: {self.workspace_root}")
    
    def _load_existing_agents(self):
        """加载已存在的代理"""
        for item in self.workspace_root.iterdir():
            if item.is_dir():
                agent_id = item.name
                if agent_id not in ['logs', 'cache', 'temp']:  # 排除系统目录
                    try:
                        agent = SkillAgent(agent_id, str(self.workspace_root))
                        self.agents[agent_id] = agent
                        logger.info(f"已加载现有代理: {agent_id}")
                    except Exception as e:
                        logger.error(f"加载代理 {agent_id} 失败: {e}")
    
    def create_agent(self, agent_id: Optional[str] = None) -> SkillAgent:
        """
        创建新的SkillAgent
        
        参数:
            agent_id: 代理ID，如果为None则自动生成
            
        返回:
            创建的SkillAgent实例
        """
        if agent_id is None:
            agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        
        if agent_id in self.agents:
            logger.warning(f"代理 {agent_id} 已存在，返回现有实例")
            return self.agents[agent_id]
        
        agent = SkillAgent(agent_id, str(self.workspace_root))
        self.agents[agent_id] = agent
        
        logger.info(f"已创建新代理: {agent_id}")
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[SkillAgent]:
        """
        获取指定代理
        
        参数:
            agent_id: 代理ID
            
        返回:
            SkillAgent实例，如果不存在则返回None
        """
        return self.agents.get(agent_id)
    
    def remove_agent(self, agent_id: str, remove_files: bool = False) -> bool:
        """
        移除代理
        
        参数:
            agent_id: 代理ID
            remove_files: 是否删除代理的文件
            
        返回:
            是否移除成功
        """
        if agent_id not in self.agents:
            logger.error(f"代理不存在: {agent_id}")
            return False
        
        try:
            agent = self.agents[agent_id]
            
            if remove_files:
                # 删除代理的工作目录
                import shutil
                shutil.rmtree(agent.work_directory, ignore_errors=True)
                logger.info(f"已删除代理文件: {agent.work_directory}")
            
            # 从管理器移除
            del self.agents[agent_id]
            logger.info(f"已移除代理: {agent_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"移除代理失败: {e}")
            return False
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """
        列出所有代理
        
        返回:
            代理信息列表
        """
        agents_info = []
        for agent_id, agent in self.agents.items():
            info = agent.get_info()
            agents_info.append(info)
        
        return agents_info
    
    def cleanup(self, max_age_days: int = 30) -> int:
        """
        清理旧文件
        
        参数:
            max_age_days: 最大保留天数
            
        返回:
            清理的文件/目录数量
        """
        import time
        current_time = time.time()
        cutoff_time = current_time - (max_age_days * 24 * 3600)
        
        cleaned_count = 0
        
        for root, dirs, files in os.walk(self.workspace_root):
            for file in files:
                file_path = Path(root) / file
                try:
                    stat_info = file_path.stat()
                    if stat_info.st_mtime < cutoff_time:
                        file_path.unlink()
                        cleaned_count += 1
                except OSError:
                    pass
            
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                try:
                    # 跳过代理目录
                    if dir_path.parent == self.workspace_root and dir_path.name in self.agents:
                        continue
                    
                    stat_info = dir_path.stat()
                    if stat_info.st_mtime < cutoff_time:
                        shutil.rmtree(dir_path, ignore_errors=True)
                        cleaned_count += 1
                except OSError:
                    pass
        
        logger.info(f"已清理 {cleaned_count} 个旧文件/目录")
        return cleaned_count

# 示例和测试代码
if __name__ == "__main__":
    # 示例1: 创建SkillAgent管理器
    manager = SkillAgentManager()
    
    # 示例2: 创建代理
    agent1 = manager.create_agent("data_processor")
    agent2 = manager.create_agent("report_generator")
    
    # 示例3: 在代理的工作目录中操作
    print(f"代理1工作目录: {agent1.pwd()}")
    
    # 创建一些文件和目录
    agent1.mkdir("data/raw")
    agent1.mkdir("data/processed")
    agent1.create_file("data/raw/sample1.txt", "这是示例文件1的内容")
    agent1.create_file("data/raw/sample2.csv", "id,name,value\n1,test,100\n2,example,200")
    agent1.create_file("config.json", '{"setting": "value", "enabled": true}')
    
    # 查看目录结构
    print("\n代理1的目录结构:")
    agent1.print_structure()
    
    # 列出目录内容
    print("\n代理1的data目录内容:")
    items = agent1.ls("data", detailed=True)
    for item in items:
        print(f"  {item['name']} ({item['type']}, {item['size'] if 'size' in item else 'N/A'} bytes)")
    
    # 查找文件
    print("\n查找JSON文件:")
    json_files = agent1.find("*.json")
    for file in json_files:
        print(f"  找到: {file}")
    
    # 读取文件内容
    print("\n读取配置文件:")
    config_content = agent1.read_file("config.json")
    if config_content:
        print(f"  配置内容: {config_content[:50]}...")
    
    # 切换目录
    print(f"\n当前目录: {agent1.pwd()}")
    agent1.cd("data/raw")
    print(f"切换后目录: {agent1.pwd()}")
    
    # 代理信息
    print("\n代理1信息:")
    info = agent1.get_info()
    print(f"  ID: {info['agent_id']}")
    print(f"  工作目录: {info['work_directory']}")
    print(f"  文件数量: {info['usage']['file_count']}")
    print(f"  总大小: {info['usage']['formatted_size']}")
    
    # 管理器功能
    print("\n所有代理:")
    agents = manager.list_agents()
    for agent_info in agents:
        print(f"  {agent_info['agent_id']}: {agent_info['usage']['formatted_size']}")
    
    # 使用独立文件系统工具
    print("\n使用独立文件系统工具:")
    fs_tool = FileSystemTool()
    structure = fs_tool.get_file_structure(agent1.pwd())
    print(f"  目录: {structure.root_path}")
    print(f"  文件数: {structure.total_files}")
    
    # 清理
    print(f"\n清理前工作空间大小: {manager.workspace_root}")
    manager.cleanup(max_age_days=0)  # 清理所有旧文件（仅示例，实际使用时小心）