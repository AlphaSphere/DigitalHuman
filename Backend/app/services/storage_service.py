"""任务级本地文件存储服务。

为每个 video task 维护 ``storage/tasks/{task_id}/`` 下的 input / intermediate / output 目录，
供上传参考视频、自定义音色/视频、写入 ASR 文本等使用，供 Celery 流水线读写路径。
"""

from pathlib import Path
from shutil import copyfileobj

from fastapi import UploadFile

from app.core.config import get_settings


def task_dir(task_id: str) -> Path:
    """获取并确保任务工作目录存在。

    用途：
        上传、写文本、touch 占位文件前的统一根路径准备。

    参数：
        task_id: 任务 ID。

    返回：
        任务根目录 Path（已创建 input、intermediate、output 子目录）。

    逻辑：
        基于配置的 storage_root，mkdir parents=True 幂等创建三级子目录。
    """
    root = get_settings().storage_root / "tasks" / task_id
    for child in ("input", "intermediate", "output"):
        (root / child).mkdir(parents=True, exist_ok=True)
    return root


def safe_name(filename: str | None, fallback: str) -> str:
    """从原始文件名提取安全后缀，或与 fallback 组合。

    用途：
        保留用户上传文件的扩展名，同时避免空文件名导致路径异常。

    参数：
        filename: 客户端原始文件名，可为 None。
        fallback: 无有效后缀时使用的基础名（如 source、custom_voice）。

    返回：
        带小写后缀的文件名，或纯 fallback。

    逻辑：
        仅采纳 Path.suffix，统一转小写后拼到 fallback 上。
    """
    if not filename:
        return fallback
    suffix = Path(filename).suffix.lower()
    return f"{fallback}{suffix}" if suffix else fallback


def save_upload(task_id: str, upload: UploadFile, name: str) -> str:
    """将 multipart 上传文件保存到任务 input 目录。

    用途：
        创建视频任务、保存生成配置时的参考视频/自定义素材上传。

    参数：
        task_id: 任务 ID。
        upload: FastAPI UploadFile 流。
        name: 保存用的逻辑文件名前缀（经 safe_name 处理扩展名）。

    返回：
        写入后的绝对或相对路径字符串。

    逻辑：
        流式 copyfileobj 到 ``input/{safe_name}``，不加载全文件到内存。
    """
    path = task_dir(task_id) / "input" / safe_name(upload.filename, name)
    with path.open("wb") as target:
        copyfileobj(upload.file, target)
    return str(path)


def write_text(task_id: str, relative: str, content: str) -> str:
    """在任务目录下写入 UTF-8 文本文件。

    用途：
        例如粘贴文案任务将 script 保存到 input/pasted_script.txt。

    参数：
        task_id: 任务 ID。
        relative: 相对任务根的路径（可含子目录）。
        content: 文本内容。

    返回：
        写入后的文件路径字符串。

    逻辑：
        自动创建父目录后 write_text encoding=utf-8。
    """
    path = task_dir(task_id) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def touch_file(task_id: str, relative: str, content: bytes = b"") -> str:
    """在任务目录下创建或覆盖二进制文件（占位/空文件）。

    用途：
        Celery 流水线或测试阶段预创建输出路径占位。

    参数：
        task_id: 任务 ID。
        relative: 相对任务根的路径。
        content: 写入字节，默认空。

    返回：
        文件路径字符串。

    逻辑：
        与 write_text 类似，使用 write_bytes。
    """
    path = task_dir(task_id) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)
