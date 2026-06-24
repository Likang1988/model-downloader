import os
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
from qfluentwidgets import PushButton, InfoBar, InfoBarPosition, TitleLabel, BodyLabel, CaptionLabel, TableWidget, SubtitleLabel
from qfluentwidgets import FluentIcon as FIF
from .downloader import FileInfo, DownloadTask
from .download_history import history_mgr
from .i18n import tr


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


# 状态颜色
STATUS_COLORS = {
    "等待下载": "#9E9E9E",
    "下载中":   "#2196F3",
    "已暂停":   "#FF9800",
    "下载完成": "#4CAF50",
    "下载失败": "#F44336",
    "已取消":   "#9E9E9E",
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
ACTIVE_STATUS = ("下载中", "连接中...")


@dataclass
class TaskItem:
    """单个下载任务的数据"""
    file_info: FileInfo
    row: int = -1
    status: str = "等待下载"
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

            # 背景
            painter.setBrush(QColor("#f0f0f0"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 5, 5)

            # 进度填充
            if pct > 0:
                fill_rect = QRect(rect)
                fill_rect.setWidth(int(rect.width() * pct / 100))
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(fill_rect, 5, 5)

            # 文字
            painter.setPen(QColor("#333"))
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

    def __init__(self, mirror_switch=None, parent=None):
        super().__init__(parent)
        self.mirror_switch = mirror_switch
        self.tasks: Dict[int, TaskItem] = {}  # row -> TaskItem
        self._next_row = 0
        self._save_path = "./models"
        self._mirror_enabled = True
        self._max_concurrent = 3
        self._active_count = 0
        self.init_ui()

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
        self.path_edit = ClickableLabel(self._save_path)
        self.path_edit.setMinimumWidth(120)
        self.path_edit.setMaximumWidth(200)
        self.path_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.path_edit.setToolTip(tr("单击选择保存目录"))
        self.path_edit.clicked.connect(self._on_browse_path)
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
        self.total_progress.setFormat("总进度: %p%")
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
        self._set_cell(row, COL_FILENAME, file_info.name)
        self._set_cell(row, COL_SOURCE,
                       "HuggingFace" if file_info.provider == "huggingface" else "ModelScope")
        self._set_cell(row, COL_STATUS, "等待下载")
        self._set_progress_cell(row, 0.0)
        self._set_cell(row, COL_DOWNLOADED, "-")
        self._set_cell(row, COL_TOTAL_SIZE, format_size(file_info.size) if file_info.size else "-")
        self._set_cell(row, COL_SPEED, "-")
        self._set_cell(row, COL_ADD_TIME, "-")

        self.tasks[row] = item
        self._update_count()
        self.log_message.emit(f"[{file_info.repo_id}] 已添加: {file_info.name}")

    def set_save_path(self, path: str):
        self._save_path = path
        if hasattr(self, 'path_edit'):
            self.path_edit.setText(path)
            self.path_edit.setToolTip(path)
        for row, ti in self.tasks.items():
            ti.save_path = path

    def set_mirror(self, enabled: bool):
        self._mirror_enabled = enabled

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
            self.pause_sel_btn.setText("暂停")
            self.pause_sel_btn.setIcon(FIF.PAUSE)
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

    # ========== 按钮操作 ==========

    def on_start_selected(self):
        """开始下载选中的任务 / 无选中则全部"""
        rows = self._get_selected_rows()
        if not rows:
            rows = list(self.tasks.keys())

        waiting = [r for r in rows
                   if r in self.tasks and self.tasks[r].status in ("等待下载", "下载失败", "已取消")]
        paused = [r for r in rows
                  if r in self.tasks and self.tasks[r].status == "已暂停"]
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

    def on_remove_selected(self):
        """移除选中的任务"""
        rows = sorted(self._get_selected_rows(), reverse=True)
        if not rows:
            return
        for r in rows:
            ti = self.tasks.pop(r, None)
            if ti:
                if ti.task:
                    ti.task.cancel()
                    if ti.thread and ti.thread.isRunning():
                        ti.thread.quit()
                        ti.thread.wait()
                self.table.removeRow(r)
                # 更新后续行的 row 映射
        # 重建 tasks 的 row 索引
        self._rebuild_row_map()
        self._update_count()
        self._update_total_progress()
        self.log_message.emit(f"已移除 {len(rows)} 个任务")

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
            file_name=ti.file_info.name,
            repo_id=ti.file_info.repo_id,
            provider=ti.file_info.provider,
            status="下载完成",
            file_size=ti.downloaded,
            save_path=ti.save_path or self._save_path,
        )
        # 自动启动下一个等待任务
        self._start_next_pending()

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
            file_name=ti.file_info.name,
            repo_id=ti.file_info.repo_id,
            provider=ti.file_info.provider,
            status="下载失败",
            file_size=ti.file_info.size or 0,
            save_path=ti.save_path or self._save_path,
        )
        self._start_next_pending()
        self.log_message.emit(f"[{ti.file_info.repo_id}] 下载失败: {ti.file_info.name} - {error}")

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
            file_name=ti.file_info.name,
            repo_id=ti.file_info.repo_id,
            provider=ti.file_info.provider,
            status="已取消",
            file_size=ti.file_info.size or 0,
            save_path=ti.save_path or self._save_path,
        )

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

        total_size = 0
        total_dl = 0
        for ti in self.tasks.values():
            sz = ti.file_info.size
            total_size += sz
            total_dl += min(ti.downloaded, sz)

        if total_size > 0:
            pct = int((total_dl / total_size) * 100)
            self.total_progress.setValue(pct)