import os
import json
import time
import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem,
    QPushButton, QHeaderView, QAbstractItemView,
    QStyledItemDelegate, QStyleOptionViewItem, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QMouseEvent
from qfluentwidgets import PushButton, InfoBar, InfoBarPosition, TitleLabel, BodyLabel, CaptionLabel, TableWidget, SubtitleLabel, isDarkTheme, LineEdit
from qfluentwidgets import FluentIcon as FIF
from .downloader import FileInfo, DownloadTask
from .download_history import history_mgr
from .i18n import tr
from .config import get_config_dir


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"


def format_eta(seconds: float) -> str:
    """将秒数格式化为剩余时间字符串"""
    if seconds < 0 or seconds > 1e7:
        return "-"
    total_sec = int(seconds)
    h, m = divmod(total_sec, 3600)
    m, s = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"


# 下载状态常量
STATUS_WAITING = "等待下载"
STATUS_DOWNLOADING = "下载中"
STATUS_PAUSED = "已暂停"
STATUS_COMPLETED = "下载完成"
STATUS_FAILED = "下载失败"
STATUS_CANCELED = "已取消"
STATUS_CONNECTING = "连接中..."

# 状态颜色
STATUS_COLORS = {
    STATUS_WAITING: "#9E9E9E",
    STATUS_DOWNLOADING: "#2196F3",
    STATUS_PAUSED: "#FF9800",
    STATUS_COMPLETED: "#4CAF50",
    STATUS_FAILED: "#F44336",
    STATUS_CANCELED: "#9E9E9E",
}

COLUMNS = ["序号", "模型ID", "文件名", "来源", "状态", "进度", "已下载", "总大小", "速度", "剩余时间"]
COL_INDEX = 0
COL_MODEL_ID = 1
COL_FILENAME = 2
COL_SOURCE = 3
COL_STATUS = 4
COL_PROGRESS = 5
COL_DOWNLOADED = 6
COL_TOTAL_SIZE = 7
COL_SPEED = 8
COL_ADD_TIME = 9

# 活跃下载状态（可暂停）
ACTIVE_STATUS = (STATUS_DOWNLOADING, STATUS_CONNECTING)

# 可重启状态（等待中、下载失败或取消后可重新开始）
RESTARTABLE_STATUS = (STATUS_WAITING, STATUS_FAILED, STATUS_CANCELED)


@dataclass
class TaskItem:
    """单个下载任务的数据"""
    file_info: FileInfo
    row: int = -1
    status: str = STATUS_WAITING
    progress: float = 0.0
    downloaded: int = 0
    speed: str = ""
    save_path: str = ""
    add_time: str = ""
    task: Optional[DownloadTask] = None
    thread: Optional[QThread] = None
    _last_bytes: int = 0
    _last_time: float = 0


class ProgressDelegate(QStyledItemDelegate):
    """进度列自定义绘制 - 带颜色的进度条"""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        progress = index.data(Qt.ItemDataRole.UserRole)  # 0~100 的浮点数
        status = index.siblingAtColumn(COL_STATUS).data(Qt.ItemDataRole.DisplayRole)
        if progress is not None:
            pct = float(progress)
            rect = QRect(option.rect).adjusted(4, 3, -4, -3)
            color = STATUS_COLORS.get(status, "#2196F3")
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 使用 isDarkTheme() 适配深色/浅色主题
            dark = isDarkTheme()
            bg_color = "#3a3a3a" if dark else "#f0f0f0"
            text_color = "#e0e0e0" if dark else "#333"

            # 背景
            painter.setBrush(QColor(bg_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 5, 5)

            # 进度填充
            if pct > 0:
                fill_rect = QRect(rect)
                fill_rect.setWidth(int(rect.width() * pct / 100))
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(fill_rect, 5, 5)

            # 文字
            painter.setPen(QColor(text_color))
            font = painter.font()
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{pct:.1f}%")
            return
        super().paint(painter, option, index)


class ClickableLabel(BodyLabel):
    """可点击的 BodyLabel"""
    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent):
        self.clicked.emit()
        super().mousePressEvent(event)


class DownloadQueueWidget(QWidget):
    """下载队列组件 - 表格形式"""
    log_message = Signal(str)

    def __init__(self, mirror_switch=None, provider="huggingface", parent=None):
        super().__init__(parent)
        self.mirror_switch = mirror_switch
        self._provider = provider
        self.tasks: Dict[int, TaskItem] = {}  # row -> TaskItem
        self._next_row = 0
        self._save_path = "./models"
        self._mirror_enabled = True
        self._max_concurrent = 3
        self._active_count = 0
        self._queue_file = os.path.join(get_config_dir(), f"queue_{provider}.json")
        self.init_ui()
        self._load_queue()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ====== 标题栏（标题 + 保存路径 + 按钮 + 总进度，全部一行）======
        header_bar = QHBoxLayout()
        header_bar.setSpacing(8)

        self.queue_title = SubtitleLabel(tr("下载队列"))
        self.count_label = CaptionLabel(tr("共 0 项"))

        # 保存路径
        self.path_prefix = BodyLabel(tr("保存路径:"))
        self.path_edit = LineEdit()
        self.path_edit.setText(self._save_path)
        self.path_edit.setMinimumWidth(100)
        self.path_edit.setMaximumWidth(220)
        self.path_edit.setReadOnly(True)
        self.path_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.path_edit.setToolTip(tr("单击选择保存目录"))
        self.path_edit.mousePressEvent = lambda e: self._on_browse_path()
        self.browse_path_btn = PushButton("📁")
        self.browse_path_btn.setFixedWidth(36)
        self.browse_path_btn.setToolTip(tr("打开保存路径"))
        self.browse_path_btn.clicked.connect(self._on_open_path)

        # 控制按钮
        self.start_sel_btn = PushButton(FIF.PLAY, tr("开始"))
        self.start_sel_btn.setFixedHeight(28)
        self.start_sel_btn.clicked.connect(self.on_start_selected)

        self.pause_sel_btn = PushButton(FIF.PAUSE, tr("暂停"))
        self.pause_sel_btn.setFixedHeight(28)
        self.pause_sel_btn.clicked.connect(self.on_pause_selected)
        self.pause_sel_btn.setEnabled(False)

        self.remove_sel_btn = PushButton(FIF.CLOSE, tr("移除"))
        self.remove_sel_btn.setFixedHeight(28)
        self.remove_sel_btn.clicked.connect(self.on_remove_selected)

        self.clear_all_btn = PushButton(FIF.BROOM, tr("清空"))
        self.clear_all_btn.setFixedHeight(28)
        self.clear_all_btn.clicked.connect(self.on_clear_all)

        # 总进度
        self.total_progress = QProgressBar()
        self.total_progress.setRange(0, 100)
        self.total_progress.setValue(0)
        self.total_progress.setFixedWidth(120)
        self.total_progress.setFixedHeight(16)
        self.total_progress.setFormat(tr("总进度: %p%"))
        self.total_progress.setVisible(False)
        self.total_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                background-color: #f0f0f0;
                text-align: center;
                font-size: 9px;
                color: #555;
            }
            QProgressBar::chunk {
                border-radius: 7px;
                background-color: #4CAF50;
            }
        """)

        header_bar.addWidget(self.queue_title)
        header_bar.addWidget(self.count_label)
        header_bar.addStretch()
        header_bar.addWidget(self.total_progress)
        header_bar.addWidget(self.path_prefix)
        header_bar.addWidget(self.path_edit)
        header_bar.addWidget(self.browse_path_btn)
        header_bar.addSpacing(8)
        header_bar.addWidget(self.start_sel_btn)
        header_bar.addWidget(self.pause_sel_btn)
        header_bar.addWidget(self.remove_sel_btn)
        header_bar.addWidget(self.clear_all_btn)
        layout.addLayout(header_bar)

        # ====== 表格 ======
        self.table = TableWidget()
        self.table.setBorderRadius(8)
        self.table.setBorderVisible(True)
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setItemDelegateForColumn(COL_PROGRESS, ProgressDelegate(self.table))
        self.table.itemSelectionChanged.connect(self._update_pause_btn_text)

        # 列宽设置
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(COL_INDEX, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_MODEL_ID, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(COL_FILENAME, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(COL_SOURCE, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_PROGRESS, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(COL_DOWNLOADED, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(COL_TOTAL_SIZE, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(COL_SPEED, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(COL_ADD_TIME, QHeaderView.ResizeMode.Interactive)
        hdr.setDefaultSectionSize(100)
        hdr.setSectionResizeMode(COL_FILENAME, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(COL_INDEX, 45)
        self.table.setColumnWidth(COL_MODEL_ID, 150)
        self.table.setColumnWidth(COL_PROGRESS, 120)
        self.table.setColumnWidth(COL_DOWNLOADED, 85)
        self.table.setColumnWidth(COL_TOTAL_SIZE, 85)
        self.table.setColumnWidth(COL_SPEED, 85)
        self.table.setColumnWidth(COL_ADD_TIME, 120)

        layout.addWidget(self.table, 1)

    # ========== 公共接口 ==========

    def add_file(self, file_info: FileInfo):
        """添加一个文件到队列"""
        # 去重检查
        for ti in self.tasks.values():
            if (ti.file_info.path == file_info.path
                    and ti.file_info.repo_id == file_info.repo_id):
                self.log_message.emit(f"[{file_info.repo_id}] 已存在: {file_info.path}")
                return

        row = self._next_row
        self._next_row += 1

        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        item = TaskItem(
            file_info=file_info,
            row=row,
            add_time=now_str,
        )

        # 插入行
        self.table.insertRow(row)
        self._set_cell(row, COL_INDEX, str(row + 1))
        self._set_cell(row, COL_MODEL_ID, file_info.repo_id)
        self._set_cell(row, COL_FILENAME, file_info.path)
        self._set_cell(row, COL_SOURCE,
                       "HuggingFace" if file_info.provider == "huggingface" else "ModelScope")
        self._set_cell(row, COL_STATUS, "等待下载")
        self._set_progress_cell(row, 0.0)
        self._set_cell(row, COL_DOWNLOADED, "-")
        self._set_cell(row, COL_TOTAL_SIZE, format_size(file_info.size) if file_info.size else "-")
        self._set_cell(row, COL_SPEED, "-")
        self._set_cell(row, COL_ADD_TIME, now_str)

        self.tasks[row] = item
        self._update_count()
        self.log_message.emit(f"[{file_info.repo_id}] 已添加: {file_info.path}")

    def set_save_path(self, path: str):
        self._save_path = path
        if hasattr(self, 'path_edit'):
            self.path_edit.setText(path)
            self.path_edit.setToolTip(path)
        for row, ti in self.tasks.items():
            ti.save_path = path
        self._save_queue()  # 立即保存路径到配置文件

    def set_mirror(self, enabled: bool):
        self._mirror_enabled = enabled

    def _save_queue(self):
        """保存队列到文件"""
        try:
            queue_data = {
                "save_path": self._save_path,
                "next_row": self._next_row,
                "tasks": []
            }
            for row, ti in self.tasks.items():
                if ti.status in (STATUS_WAITING, STATUS_PAUSED, STATUS_FAILED):
                    task_data = {
                        "row": row,
                        "file_info": {
                            "name": ti.file_info.name,
                            "size": ti.file_info.size,
                            "path": ti.file_info.path,
                            "repo_id": ti.file_info.repo_id,
                            "repo_type": ti.file_info.repo_type,
                            "provider": ti.file_info.provider,
                        },
                        "status": ti.status,
                        "downloaded": ti.downloaded,
                        "save_path": ti.save_path,
                        "add_time": ti.add_time,
                    }
                    queue_data["tasks"].append(task_data)
            with open(self._queue_file, "w", encoding="utf-8") as f:
                json.dump(queue_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_queue(self):
        """从文件加载队列"""
        if not os.path.exists(self._queue_file):
            return
        try:
            with open(self._queue_file, "r", encoding="utf-8") as f:
                queue_data = json.load(f)
            if "save_path" in queue_data:
                self._save_path = queue_data["save_path"]
                # 立即更新 UI 显示路径
                if hasattr(self, 'path_edit'):
                    self.path_edit.setText(self._save_path)
                    self.path_edit.setToolTip(self._save_path)
            if "next_row" in queue_data:
                self._next_row = queue_data["next_row"]
            if "tasks" in queue_data:
                tasks = queue_data["tasks"]
                if not tasks:
                    return
                
                max_row = max(t["row"] for t in tasks) + 1
                self.table.setRowCount(max_row)
                
                for task_data in tasks:
                    fi_data = task_data.get("file_info", {})
                    file_info = FileInfo(
                        name=fi_data.get("name", ""),
                        size=fi_data.get("size", 0),
                        path=fi_data.get("path", ""),
                        repo_id=fi_data.get("repo_id", ""),
                        repo_type=fi_data.get("repo_type", "model"),
                        provider=fi_data.get("provider", "huggingface"),
                    )
                    row = task_data.get("row", self._next_row)
                    status = task_data.get("status", STATUS_WAITING)
                    downloaded = task_data.get("downloaded", 0)
                    save_path = task_data.get("save_path", self._save_path)
                    add_time = task_data.get("add_time", "")
                    
                    if row >= self._next_row:
                        self._next_row = row + 1
                    
                    item = TaskItem(
                        file_info=file_info,
                        row=row,
                        status=status,
                        downloaded=downloaded,
                        save_path=save_path,
                        add_time=add_time,
                    )
                    
                    self._set_cell(row, COL_INDEX, str(row + 1))
                    self._set_cell(row, COL_MODEL_ID, file_info.repo_id)
                    self._set_cell(row, COL_FILENAME, file_info.path)
                    self._set_cell(row, COL_SOURCE,
                                   "HuggingFace" if file_info.provider == "huggingface" else "ModelScope")
                    self._set_cell(row, COL_STATUS, status)
                    if status == STATUS_PAUSED and downloaded > 0 and file_info.size:
                        progress = downloaded / file_info.size * 100
                    else:
                        progress = 0.0
                    self._set_progress_cell(row, progress)
                    self._set_cell(row, COL_DOWNLOADED, format_size(downloaded) if downloaded > 0 else "-")
                    self._set_cell(row, COL_TOTAL_SIZE, format_size(file_info.size) if file_info.size else "-")
                    self._set_cell(row, COL_SPEED, "-")
                    self._set_cell(row, COL_ADD_TIME, add_time)
                    
                    self.tasks[row] = item
                
                self._update_count()
                self._update_pause_btn_text()
                self.log_message.emit(tr(f"已恢复 {len(tasks)} 个任务"))
        except Exception:
            pass

    def retranslateUi(self):
        self.queue_title.setText(tr("下载队列"))
        self.count_label.setText(tr("共 0 项").format(self.table.rowCount()))
        self.path_prefix.setText(tr("保存路径:"))
        self.path_edit.setToolTip(tr("单击选择保存目录"))
        self.browse_path_btn.setToolTip(tr("打开保存路径"))
        self.start_sel_btn.setText(tr("开始"))
        self.pause_sel_btn.setText(tr("暂停"))
        self.remove_sel_btn.setText(tr("移除"))
        self.clear_all_btn.setText(tr("清空"))
        col_labels = [tr("序号"), tr("模型ID"), tr("文件名"), tr("来源"),
                      tr("状态"), tr("进度"), tr("已下载"), tr("总大小"),
                      tr("速度"), tr("剩余时间")]
        self.table.setHorizontalHeaderLabels(col_labels)

    def _on_browse_path(self):
        """浏览并选择保存路径"""
        from PySide6.QtWidgets import QFileDialog
        default = os.path.abspath(self._save_path) if self._save_path else os.path.join(os.path.expanduser("~"), "Downloads", "models")
        path = QFileDialog.getExistingDirectory(self, "选择保存目录", default)
        if path:
            self.set_save_path(path)

    def _on_open_path(self):
        """打开保存路径所在文件夹"""
        path = os.path.abspath(self._save_path)
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        os.startfile(path)

    def _update_pause_btn_text(self):
        """根据选中的任务状态更新暂停/继续按钮文本"""
        rows = self._get_selected_rows()
        if not rows:
            has_active = any(t.status in ACTIVE_STATUS for t in self.tasks.values())
            has_paused = any(t.status == "已暂停" for t in self.tasks.values())
            if has_paused and not has_active:
                self.pause_sel_btn.setText(tr("恢复"))
                self.pause_sel_btn.setIcon(FIF.PLAY)
                self.pause_sel_btn.setEnabled(True)
            elif has_active:
                self.pause_sel_btn.setText(tr("暂停"))
                self.pause_sel_btn.setIcon(FIF.PAUSE)
                self.pause_sel_btn.setEnabled(True)
            else:
                self.pause_sel_btn.setEnabled(False)
            return

        all_paused = all(
            r in self.tasks and self.tasks[r].status == "已暂停"
            for r in rows
        )
        all_active = all(
            r in self.tasks and self.tasks[r].status in ACTIVE_STATUS
            for r in rows
        )

        if all_paused:
            self.pause_sel_btn.setText("继续")
            self.pause_sel_btn.setIcon(FIF.PLAY)
            self.pause_sel_btn.setEnabled(True)
        elif all_active:
            self.pause_sel_btn.setText("暂停")
            self.pause_sel_btn.setIcon(FIF.PAUSE)
            self.pause_sel_btn.setEnabled(True)
        else:
            self.pause_sel_btn.setText("暂停")
            self.pause_sel_btn.setIcon(FIF.PAUSE)
            self.pause_sel_btn.setEnabled(False)

    def get_active_count(self):
        """获取当前正在下载的任务数量"""
        return sum(1 for t in self.tasks.values() if t.status in ACTIVE_STATUS)

    def _shutdown(self):
        """安全关闭所有下载任务，确保线程正确退出"""
        # 先断开所有信号连接，防止 cancel 后触发回调
        for ti in self.tasks.values():
            if ti.task:
                try:
                    ti.task.progress_updated.disconnect()
                    ti.task.download_completed.disconnect()
                    ti.task.download_failed.disconnect()
                    ti.task.download_canceled.disconnect()
                    ti.task.download_paused.disconnect()
                    ti.task.status_changed.disconnect()
                except Exception:
                    pass
        
        # 保存当前活跃的任务状态
        for row, ti in self.tasks.items():
            if ti.status in ACTIVE_STATUS:
                ti.status = STATUS_PAUSED
                self._set_cell(row, COL_STATUS, STATUS_PAUSED)
        
        # 取消并等待所有线程退出
        for ti in self.tasks.values():
            if ti.task:
                ti.task.cancel()
            if ti.thread and ti.thread.isRunning():
                ti.thread.quit()
                ti.thread.wait(100)  # 最多等待100ms
        
        # 保存队列
        self._active_count = 0
        self._update_pause_btn_text()
        self._save_queue()

    # ========== 按钮操作 ==========

    def on_start_selected(self):
        """开始下载选中的任务 / 无选中则全部"""
        rows = self._get_selected_rows()
        if not rows:
            rows = list(self.tasks.keys())

        waiting = [r for r in rows
                   if r in self.tasks and self.tasks[r].status in ("等待下载", "下载失败", "已取消")]
        paused = [r for r in rows
                  if r in self.tasks and self.tasks[r].status == "已暂停" and self.tasks[r].task]
        waiting.extend([r for r in rows
                       if r in self.tasks and self.tasks[r].status == "已暂停" and not self.tasks[r].task])
        if not waiting and not paused:
            self.log_message.emit("没有可下载的任务")
            return

        if not self._save_path:
            from PySide6.QtWidgets import QFileDialog
            default = os.path.join(os.path.expanduser("~"), "Downloads", "models")
            path = QFileDialog.getExistingDirectory(self, "选择保存目录", default)
            if not path:
                return
            self.set_save_path(path)

        # 先恢复已暂停的任务
        for r in paused:
            ti = self.tasks.get(r)
            if ti and ti.task:
                ti.task.resume()
                ti.status = "下载中"
                self._set_cell(r, COL_STATUS, "下载中")
                self._set_cell(r, COL_SPEED, "")
                self._active_count += 1

        mirror = self.mirror_switch.isChecked() if self.mirror_switch else False

        for row in waiting:
            if self._active_count >= self._max_concurrent:
                break
            self._start_download(row, mirror)
        self._update_pause_btn_text()

    def on_pause_selected(self):
        """暂停/恢复选中的下载任务（切换操作）"""
        rows = self._get_selected_rows()
        if not rows:
            rows = list(self.tasks.keys())

        # 判断操作类型：只要有一个已暂停的任务就执行恢复
        has_paused = any(
            r in self.tasks and self.tasks[r].status == "已暂停"
            for r in rows
        )

        if has_paused:
            resumed = 0
            for r in rows:
                ti = self.tasks.get(r)
                if ti and ti.status == "已暂停" and ti.task:
                    ti.task.resume()
                    ti.status = "下载中"
                    self._set_cell(r, COL_STATUS, "下载中")
                    self._set_cell(r, COL_SPEED, "")
                    resumed += 1
            self._active_count = sum(1 for t in self.tasks.values() if t.status in ACTIVE_STATUS)
            if resumed:
                self.log_message.emit(f"已恢复 {resumed} 个任务")
        else:
            paused = 0
            for r in rows:
                ti = self.tasks.get(r)
                if ti and ti.status in ACTIVE_STATUS and ti.task:
                    ti.task.pause()
                    ti.status = "已暂停"
                    self._set_cell(r, COL_STATUS, "已暂停")
                    paused += 1
            self._active_count = sum(1 for t in self.tasks.values() if t.status in ACTIVE_STATUS)
            if paused:
                self.log_message.emit(f"已暂停 {paused} 个任务")
            # 暂停后自动启动等待中的任务填补槽位
            self._start_next_pending()
        self._update_pause_btn_text()
        self._save_queue()

    def on_remove_selected(self):
        """移除选中的任务"""
        rows = sorted(self._get_selected_rows(), reverse=True)
        if not rows:
            return
        
        # 检查是否有需要删除本地文件的任务
        tasks_to_remove = []
        has_local_files = []
        for r in rows:
            ti = self.tasks.get(r)
            if ti:
                tasks_to_remove.append((r, ti))
                # 检查本地文件是否存在
                file_path = os.path.join(ti.save_path or self._save_path, ti.file_info.repo_id, ti.file_info.path)
                if os.path.exists(file_path):
                    has_local_files.append((r, ti, file_path))
        
        delete_files = False
        
        # 如果有本地文件，弹出确认对话框
        if has_local_files:
            from PySide6.QtWidgets import QMessageBox
            file_names = "\n".join([f"• {ti.file_info.path}" for _, ti, _ in has_local_files[:5]])
            if len(has_local_files) > 5:
                file_names += f"\n... 还有 {len(has_local_files) - 5} 个文件"
            
            msg_box = QMessageBox(self.window())
            msg_box.setWindowTitle(tr("确认删除"))
            msg_box.setText(tr("以下文件已存在于本地：\n{0}\n\n是否同时删除本地文件？").format(file_names))
            msg_box.setStandardButtons(QMessageBox.No | QMessageBox.Yes | QMessageBox.Cancel)
            msg_box.button(QMessageBox.No).setText(tr("仅移除任务"))
            msg_box.button(QMessageBox.Yes).setText(tr("同时删除文件"))
            msg_box.button(QMessageBox.Cancel).setText(tr("取消"))
            msg_box.setDefaultButton(QMessageBox.No)
            
            result = msg_box.exec()
            if result == QMessageBox.Cancel:
                return
            delete_files = (result == QMessageBox.Yes)
        
        # 先停止所有下载任务
        for r, ti in tasks_to_remove:
            if ti.task:
                ti.task.cancel()
            if ti.thread and ti.thread.isRunning():
                ti.thread.quit()
                ti.thread.wait(500)  # 等待最多500ms
        
        # 删除本地文件（在任务停止后）
        if delete_files:
            import time
            time.sleep(0.1)  # 给文件句柄一些时间释放
            for _, ti, file_path in has_local_files:
                try:
                    os.remove(file_path)
                    self.log_message.emit(f"[{ti.file_info.repo_id}] 已删除本地文件: {ti.file_info.path}")
                except Exception as e:
                    self.log_message.emit(f"[{ti.file_info.repo_id}] 删除失败: {ti.file_info.path} - {str(e)}")
        
        # 执行移除
        for r, ti in tasks_to_remove:
            self.tasks.pop(r, None)
            self.table.removeRow(r)
        
        # 重建 tasks 的 row 索引
        self._rebuild_row_map()
        self._update_count()
        self._update_total_progress()
        self._save_queue()
        self.log_message.emit(f"已移除 {len(tasks_to_remove)} 个任务")

    def on_clear_all(self):
        """清空整个队列"""
        if not self.tasks:
            return
        # 取消所有下载任务
        for ti in self.tasks.values():
            if ti.task:
                ti.task.cancel()
                if ti.thread and ti.thread.isRunning():
                    ti.thread.quit()
                    ti.thread.wait()
        self.tasks.clear()
        self.table.setRowCount(0)
        self._next_row = 0
        self._active_count = 0
        self._update_count()
        self._update_total_progress()
        self.log_message.emit("已清空下载队列")

    # ========== 内部方法 ==========

    def _start_download(self, row: int, mirror: bool):
        ti = self.tasks.get(row)
        if not ti:
            return

        ti.task = DownloadTask(ti.file_info, self._save_path, mirror)
        ti.thread = QThread()
        ti.task.moveToThread(ti.thread)

        # 连接信号
        ti.task.progress_updated.connect(
            lambda tid, cur, total: self._on_progress(row, cur, total))
        ti.task.download_completed.connect(
            lambda tid: self._on_completed(row))
        ti.task.download_failed.connect(
            lambda tid, err: self._on_failed(row, err))
        ti.task.download_canceled.connect(
            lambda tid: self._on_canceled(row))
        ti.task.download_paused.connect(
            lambda tid: self._on_paused(row))
        ti.task.status_changed.connect(
            lambda tid, st: self._on_status_changed(row, st))

        ti.thread.started.connect(ti.task.run)
        ti.thread.start()

        ti.status = "下载中"
        ti._last_time = time.time()
        ti._last_bytes = 0
        self._set_cell(row, COL_STATUS, "下载中")
        self._set_cell(row, COL_SPEED, "")
        self._active_count += 1
        self._update_pause_btn_text()

    def _on_progress(self, row: int, current: int, total: int):
        ti = self.tasks.get(row)
        if not ti:
            return

        ti.downloaded = current
        pct = (current / total) * 100 if total > 0 else 0

        # 计算速度
        now = time.time()
        elapsed = now - ti._last_time
        if elapsed >= 0.5:
            diff = current - ti._last_bytes
            if diff >= 0 and elapsed > 0:
                speed_bps = diff / elapsed
                ti.speed = format_size(int(speed_bps)) + "/s"
                # 计算剩余时间
                remaining = total - current
                eta_sec = remaining / speed_bps if speed_bps > 0 else -1
                self._set_cell(row, COL_ADD_TIME, format_eta(eta_sec))
            ti._last_time = now
            ti._last_bytes = current

        # 更新单元格
        self._set_progress_cell(row, pct)
        self._set_cell(row, COL_DOWNLOADED, format_size(current))
        self._set_cell(row, COL_SPEED, ti.speed)
        self._update_total_progress()

    def _on_completed(self, row: int):
        ti = self.tasks.get(row)
        if not ti:
            return
        ti.status = "下载完成"
        self._set_cell(row, COL_STATUS, "下载完成")
        self._set_progress_cell(row, 100)
        self._set_cell(row, COL_DOWNLOADED, format_size(ti.downloaded))
        self._set_cell(row, COL_SPEED, "")
        ti.speed = ""
        self._cleanup_thread(row)
        self._active_count = max(0, self._active_count - 1)
        self._update_total_progress()
        # 写入历史记录
        history_mgr.add_record(
            file_name=ti.file_info.path,
            repo_id=ti.file_info.repo_id,
            provider=ti.file_info.provider,
            status="下载完成",
            file_size=ti.downloaded,
            save_path=ti.save_path or self._save_path,
        )
        # 自动启动下一个等待任务
        self._start_next_pending()
        self._save_queue()

    def _on_failed(self, row: int, error: str):
        ti = self.tasks.get(row)
        if not ti:
            return
        ti.status = "下载失败"
        self._set_cell(row, COL_STATUS, "下载失败")
        self._set_cell(row, COL_SPEED, "")
        self._cleanup_thread(row)
        self._active_count = max(0, self._active_count - 1)
        self._update_total_progress()
        # 写入历史记录
        history_mgr.add_record(
            file_name=ti.file_info.path,
            repo_id=ti.file_info.repo_id,
            provider=ti.file_info.provider,
            status="下载失败",
            file_size=ti.file_info.size or 0,
            save_path=ti.save_path or self._save_path,
        )
        self._start_next_pending()
        self.log_message.emit(f"[{ti.file_info.repo_id}] 下载失败: {ti.file_info.path} - {error}")
        self._save_queue()

    def _on_canceled(self, row: int):
        ti = self.tasks.get(row)
        if not ti:
            return
        ti.status = "已取消"
        self._set_cell(row, COL_STATUS, "已取消")
        self._set_cell(row, COL_SPEED, "")
        self._cleanup_thread(row)
        self._active_count = max(0, self._active_count - 1)
        # 写入历史记录
        history_mgr.add_record(
            file_name=ti.file_info.path,
            repo_id=ti.file_info.repo_id,
            provider=ti.file_info.provider,
            status="已取消",
            file_size=ti.file_info.size or 0,
            save_path=ti.save_path or self._save_path,
        )
        self._save_queue()

    def _on_paused(self, row: int):
        ti = self.tasks.get(row)
        if not ti:
            return
        # 防止 on_pause_selected 已处理过状态后，信号再触发的重复操作
        if ti.status == "已暂停":
            return
        ti.status = "已暂停"
        self._set_cell(row, COL_STATUS, "已暂停")
        self._set_cell(row, COL_SPEED, "")
        self._active_count = max(0, self._active_count - 1)
        self._start_next_pending()

    def _on_status_changed(self, row: int, status: str):
        ti = self.tasks.get(row)
        if not ti:
            return
        ti.status = status
        self._set_cell(row, COL_STATUS, status)

    def _cleanup_thread(self, row: int):
        ti = self.tasks.get(row)
        if ti and ti.thread and ti.thread.isRunning():
            ti.thread.quit()
            ti.thread.wait()

    def _start_next_pending(self):
        """完成一个任务后自动启动下一个等待任务"""
        mirror = self.mirror_switch.isChecked() if self.mirror_switch else False
        for r, ti in self.tasks.items():
            if ti.status in ("等待下载", "下载失败", "已取消"):
                if self._active_count >= self._max_concurrent:
                    break
                self._start_download(r, mirror)

    def _get_selected_rows(self) -> list:
        """获取当前选中行号列表"""
        return sorted(set(
            idx.row() for idx in self.table.selectedIndexes()
        ))

    def _rebuild_row_map(self):
        """行删除后重建索引"""
        new_tasks = {}
        for r in range(self.table.rowCount()):
            if r in self.tasks:
                ti = self.tasks[r]
                ti.row = r
                new_tasks[r] = ti
        self.tasks = new_tasks
        self._next_row = self.table.rowCount()

    def _set_cell(self, row: int, col: int, text: str):
        if row < self.table.rowCount():
            item = self.table.item(row, col)
            if item is None:
                item = QTableWidgetItem()
                self.table.setItem(row, col, item)
            item.setText(text)

    def _set_progress_cell(self, row: int, pct: float):
        """设置进度单元格（使用 UserRole 存储数值供 Delegate 使用）"""
        if row < self.table.rowCount():
            item = self.table.item(row, COL_PROGRESS)
            if item is None:
                item = QTableWidgetItem()
                self.table.setItem(row, COL_PROGRESS, item)
            item.setData(Qt.ItemDataRole.DisplayRole, f"{pct:.1f}%")
            item.setData(Qt.ItemDataRole.UserRole, pct)

    def _update_count(self):
        self.count_label.setText(f"共 {len(self.tasks)} 项")

    def _update_total_progress(self):
        if not self.tasks:
            self.total_progress.setVisible(False)
            return

        self.total_progress.setVisible(True)
        total_size = 0
        total_dl = 0
        for ti in self.tasks.values():
            sz = ti.file_info.size
            total_size += sz
            total_dl += min(ti.downloaded, sz)

        if total_size > 0:
            pct = int((total_dl / total_size) * 100)
            self.total_progress.setValue(pct)