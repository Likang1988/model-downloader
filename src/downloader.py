import os
import re
import requests
import urllib3
from typing import List, Dict, Optional
from PySide6.QtCore import QObject, Signal, QMutex, QMutexLocker

# 关闭 SSL 警告（用于 modelscope 等有 SSL 兼容问题的站点）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 默认请求头
DEFAULT_HEADERS = {
    "User-Agent": "ModelDownloader/1.0 (Windows; +https://github.com) Python/3.x",
    "Accept": "application/json"
}


def get_auth_headers(provider: str) -> dict:
    """根据 provider 获取带 Token 认证的请求头（如果有配置的话）"""
    from .config import cfg
    headers = dict(DEFAULT_HEADERS)
    token = ""
    if provider == "huggingface":
        token = cfg.get(cfg.hf_token) or ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif provider == "modelscope":
        token = cfg.get(cfg.ms_token) or ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
    return headers


# 从 download_queue 导入状态常量，避免硬编码
def _get_status_connecting():
    from .download_queue import STATUS_CONNECTING
    return STATUS_CONNECTING

def _get_status_downloading():
    from .download_queue import STATUS_DOWNLOADING
    return STATUS_DOWNLOADING


class FileInfo:
    def __init__(self, name: str, size: int, path: str, repo_id: str, repo_type: str, provider: str):
        self.name = name
        self.size = size
        self.path = path
        self.repo_id = repo_id
        self.repo_type = repo_type
        self.provider = provider
        self.selected = False


class DownloadTask(QObject):
    progress_updated = Signal(object, object, object)
    download_completed = Signal(object)
    download_failed = Signal(object, str)
    download_canceled = Signal(object)
    download_paused = Signal(object)
    status_changed = Signal(object, str)

    def __init__(self, file_info: FileInfo, save_path: str, mirror_enabled: bool = False):
        super().__init__()
        self.file_info = file_info
        self.save_path = save_path
        self.mirror_enabled = mirror_enabled
        self.task_id = id(self)
        self.canceled = False
        self._paused = False
        self.current_size = 0
        self.total_size = 0
        self._mutex = QMutex()
        self._response = None  # HTTP 响应对象

    def get_download_url(self) -> str:
        provider = self.file_info.provider
        repo_id = self.file_info.repo_id
        path = self.file_info.path

        if provider == "huggingface":
            from .config import cfg
            token = cfg.get(cfg.hf_token) or ""
            if token and self.mirror_enabled:
                return f"https://huggingface.co/{repo_id}/resolve/main/{path}"
            base = "https://hf-mirror.com" if self.mirror_enabled else "https://huggingface.co"
            return f"{base}/{repo_id}/resolve/main/{path}"
        elif provider == "modelscope":
            repo_type = self.file_info.repo_type
            if repo_type == "dataset":
                return f"https://www.modelscope.cn/datasets/{repo_id}/resolve/master/{path}"
            return f"https://www.modelscope.cn/{repo_id}/resolve/master/{path}"
        return ""

    def run(self):
        url = self.get_download_url()
        if not url:
            self._safe_emit_failed("无效的下载URL")
            return

        try:
            self._safe_emit_status_changed(_get_status_connecting())
            headers = get_auth_headers(self.file_info.provider)
            
            file_path = os.path.join(self.save_path, self.file_info.repo_id, self.file_info.path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            resume_size = 0
            if os.path.exists(file_path):
                resume_size = os.path.getsize(file_path)
            
            if resume_size > 0:
                headers["Range"] = f"bytes={resume_size}-"
            
            self._response = requests.get(url, stream=True, timeout=30, headers=headers)
            self._response.raise_for_status()

            total_size = int(self._response.headers.get("content-length", 0)) or 0
            if resume_size > 0:
                content_range = self._response.headers.get("content-range", "")
                if content_range:
                    match = re.search(r"/(\d+)$", content_range)
                    if match:
                        total_size = int(match.group(1))
                else:
                    total_size += resume_size
            
            self.total_size = total_size
            self.current_size = resume_size
            self._safe_emit_status_changed(_get_status_downloading())

            mode = "ab" if resume_size > 0 else "wb"
            with open(file_path, mode) as f:
                for chunk in self._response.iter_content(chunk_size=8192):
                    if self.canceled:
                        f.close()  # 先关闭文件
                        self._cleanup_file()
                        self._safe_emit_canceled()
                        return

                    if self._paused:
                        self._safe_emit_paused()
                        self._wait_for_resume()

                    if chunk:
                        f.write(chunk)
                        self.current_size += len(chunk)
                        self._safe_emit_progress(self.current_size, total_size)

            self._safe_emit_completed()
        except Exception as e:
            self._safe_emit_failed(str(e))
        finally:
            # 确保响应被关闭
            if self._response:
                self._response.close()
                self._response = None

    def _safe_emit_progress(self, current, total):
        try:
            self.progress_updated.emit(self.task_id, current, total)
        except RuntimeError:
            pass

    def _safe_emit_status_changed(self, status):
        try:
            self.status_changed.emit(self.task_id, status)
        except RuntimeError:
            pass

    def _safe_emit_completed(self):
        try:
            self.download_completed.emit(self.task_id)
        except RuntimeError:
            pass

    def _safe_emit_failed(self, error):
        try:
            self.download_failed.emit(self.task_id, error)
        except RuntimeError:
            pass

    def _safe_emit_canceled(self):
        try:
            self.download_canceled.emit(self.task_id)
        except RuntimeError:
            pass

    def _safe_emit_paused(self):
        try:
            self.download_paused.emit(self.task_id)
        except RuntimeError:
            pass

    def _cleanup_file(self):
        """删除未完成的下载文件"""
        file_path = os.path.join(self.save_path, self.file_info.repo_id, self.file_info.path)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

    def _wait_for_resume(self):
        import time
        while self._paused and not self.canceled:
            time.sleep(0.1)

    def pause(self):
        locker = QMutexLocker(self._mutex)
        self._paused = True

    def resume(self):
        locker = QMutexLocker(self._mutex)
        self._paused = False

    def cancel(self):
        self.canceled = True
        self._paused = False
        # 立即关闭 HTTP 响应，中断 iter_content 循环
        if self._response:
            try:
                self._response.close()
            except Exception:
                pass
            self._response = None

    @property
    def is_paused(self):
        return self._paused


class RepoProvider:
    @staticmethod
    def list_files(provider: str, repo_id: str, repo_type: str = "model", mirror_enabled: bool = False) -> List[FileInfo]:
        """获取仓库文件列表，失败时自动尝试另一种类型"""
        debug_msgs = []
        try:
            files, dbg = RepoProvider._try_list_files(provider, repo_id, repo_type, mirror_enabled)
            debug_msgs.append(dbg)
            # HF/ModelScope 内部已自动尝试两种类型路径，无需 fallback
            if not files and provider not in ("huggingface", "modelscope") and repo_type in ("model", "dataset"):
                alt_type = "dataset" if repo_type == "model" else "model"
                files, dbg = RepoProvider._try_list_files(provider, repo_id, alt_type, mirror_enabled)
                debug_msgs.append(dbg)
            if not files:
                all_debug = "; ".join(m for sub in debug_msgs for m in sub)
                raise Exception(f"所有API端点均返回空\n{all_debug}")
            return files
        except Exception as e:
            all_debug = "; ".join(m for sub in debug_msgs for m in sub)
            raise Exception(f"获取文件列表失败: {str(e)}\n{all_debug}")

    @staticmethod
    def _try_list_files(provider: str, repo_id: str, repo_type: str, mirror_enabled: bool = False):
        files = []
        debug = []
        auth_headers = get_auth_headers(provider)
        try:
            if provider == "huggingface":
                urls_to_try = ["https://hf-mirror.com", "https://huggingface.co"]
                if not mirror_enabled:
                    urls_to_try.reverse()

                # 同时尝试 models 和 datasets 两个路径的递归 tree API
                types = ["models", "datasets"]
                for base_url in urls_to_try:
                    for repo_type_path in types:
                        api_url = f"{base_url}/api/{repo_type_path}/{repo_id}/tree/main?recursive=True"
                        try:
                            resp = requests.get(api_url, timeout=15, headers=auth_headers, verify=False)
                            debug.append(f"{api_url} → {resp.status_code}")
                            if resp.status_code in (401, 403, 404):
                                debug[-1] += " (跳过)"
                                continue
                            resp.raise_for_status()
                            data = resp.json()
                            debug[-1] += f" (files={len(data)})"
                            if isinstance(data, list) and data:
                                for item in data:
                                    if item.get("type") in ("directory", "tree"):
                                        continue  # 跳过目录
                                    files.append(FileInfo(
                                        name=item.get("path", "").split("/")[-1],
                                        size=item.get("size", 0),
                                        path=item.get("path", ""),
                                        repo_id=repo_id,
                                        repo_type=repo_type,
                                        provider=provider
                                    ))
                                break
                            else:
                                debug[-1] += " (无文件)"
                        except requests.exceptions.Timeout:
                            debug.append(f"{api_url} → 超时")
                            continue
                        except requests.exceptions.ConnectionError:
                            debug.append(f"{api_url} → 连接失败")
                            continue
                    if files:
                        break
                if not files:
                    debug.append(f"⚠ {repo_id} 无结果")

            elif provider == "modelscope":
                # 自动尝试 models 和 datasets 两个 API（dataset 树 API 可能较慢，给 30s）
                # 注意：models 使用 /repo/files，datasets 使用 /repo/tree
                api_templates = [
                    f"https://www.modelscope.cn/api/v1/models/{repo_id}/repo/files?Revision=master&Recursive=True",
                    f"https://www.modelscope.cn/api/v1/datasets/{repo_id}/repo/tree?Revision=master&Recursive=True",
                ]
                for idx, api_url in enumerate(api_templates):
                    ms_timeout = 30 if idx > 0 else 15  # datasets 给更长超时
                    try:
                        resp = requests.get(
                            api_url, timeout=ms_timeout,
                            headers=auth_headers,
                            verify=False
                        )
                        debug.append(f"{api_url} → {resp.status_code}")
                        if resp.status_code in (401, 403, 404):
                            debug[-1] += " (跳过)"
                            continue
                        resp.raise_for_status()
                        data = resp.json()
                        # 兼容两种响应格式：Files 和 Tree
                        file_list_raw = data.get("Data", {}).get("Files", []) or data.get("Data", {}).get("Tree", []) or []
                        debug[-1] += f" (raw_files={len(file_list_raw)})"
                        for f in file_list_raw:
                            # 过滤目录类型（tree）和 None 类型
                            f_type = f.get("Type", "")
                            if f_type in ("tree", "directory", None):
                                continue
                            files.append(FileInfo(
                                name=f.get("Name", ""),
                                size=f.get("Size", 0),
                                path=f.get("Path", ""),
                                repo_id=repo_id,
                                repo_type=repo_type,
                                provider=provider
                            ))
                        debug[-1] += f" (files={len(files)})"
                        if files:
                            break
                    except requests.exceptions.Timeout:
                        debug.append(f"{api_url} → 超时")
                        continue
                    except requests.exceptions.ConnectionError:
                        debug.append(f"{api_url} → 连接失败")
                        continue
                if not files:
                    debug.append(f"⚠ {repo_id} 无结果")

        except requests.exceptions.SSLError:
            raise Exception("SSL连接错误，请检查网络环境或尝试使用HF镜像下载")
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            return [], debug
        except Exception:
            raise

        return files, debug

    @staticmethod
    def search_models(provider: str, query: str, repo_type: str = "model") -> List[Dict]:
        results = []
        try:
            if provider == "huggingface":
                url = f"https://huggingface.co/api/models?search={query}&limit=20"
                resp = requests.get(url, timeout=15, headers=DEFAULT_HEADERS)
                resp.raise_for_status()
                for item in resp.json():
                    results.append({
                        "id": item.get("id", ""),
                        "name": item.get("id", "").split("/")[-1],
                        "author": item.get("id", "").split("/")[0],
                        "description": item.get("description", ""),
                        "downloads": item.get("downloads", 0),
                        "likes": item.get("likes", 0)
                    })
            elif provider == "modelscope":
                url = f"https://www.modelscope.cn/api/v1/models?search={query}&limit=20"
                resp = requests.get(url, timeout=15, headers=DEFAULT_HEADERS, verify=False)
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("Data", []):
                    results.append({
                        "id": item.get("Name", ""),
                        "name": item.get("Name", "").split("/")[-1],
                        "author": item.get("Name", "").split("/")[0],
                        "description": item.get("Description", ""),
                        "downloads": item.get("DownloadCount", 0),
                        "likes": item.get("LikeCount", 0)
                    })
        except Exception as e:
            raise e
        return results