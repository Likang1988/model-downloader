"""下载历史记录管理模块 — 持久化存储下载历史，支持筛选、重新下载、打开位置等操作。"""

import os
import json
import datetime
from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QHeaderView, QAbstractItemView, QTableWidgetItem, QStyledItemDelegate,
    QStyleOptionViewItem, QStyle
)
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPainter, QColor, QMouseEvent
from qfluentwidgets import (
    TableWidget, PushButton, BodyLabel, CaptionLabel, SubtitleLabel,
    InfoBar, InfoBarPosition, PrimaryPushButton, ToolButton,
    FluentIcon as FIF, MessageDialog
)
from .config import get_config_dir, get_config_path
from .i18n import tr


def format_size(size: int) -> str:
    if size < 0:
        return "-"
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"


# 列定义
HIST_COLUMNS = ["序号", "文件名", "模型ID", "来源", "状态", "大小", "完成时间", "保存路径"]
HIST_IDX = 0
HIST_NAME = 1
HIST_REPO_ID = 2
HIST_SOURCE = 3
HIST_STATUS = 4
HIST_SIZE = 5
HIST_TIME = 6
HIST_PATH = 7


class HistoryDelegate(QStyledItemDelegate):
    """状态列自定义颜色绘制"""

    STATUS_COLORS = {
        "下载完成": "#4CAF50",
        "下载失败": "#F44336",
        "已取消": "#9E9E9E",
        "部分完成": "#FF9800",
    }

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        status_text = index.data(Qt.ItemDataRole.DisplayRole)
        if status_text in self.STATUS_COLORS:
            rect = QRect(option.rect).adjusted(4, 4, -4, -4)
            color = QColor(self.STATUS_COLORS[status_text])
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(color.lighter(150))
            painter.setPen(color)
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QColor("#333"))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, status_text)
            return
        super().paint(self, painter, option, index)


class HistoryManager:
    """下载历史记录的持久化管理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._records: List[Dict[str, Any]] = []
        self._load()

    def _get_file_path(self) -> str:
        return os.path.join(get_config_dir(), "history.json")

    def _load(self):
        path = self._get_file_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._records = json.load(f)
            except Exception:
                self._records = []
        else:
            self._records = []

    def _save(self):
        path = self._get_file_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_record(
        self,
        file_name: str,
        repo_id: str,
        provider: str,
        status: str,
        file_size: int,
        save_path: str,
    ):
        """追加一条历史记录"""
        record = {
            "id": len(self._records) + 1,
            "file_name": file_name,
            "repo_id": repo_id,
            "provider": provider,          # "huggingface" | "modelscope"
            "status": status,             # "下载完成" | "下载失败" | "已取消"
            "file_size": file_size,
            "save_path": save_path,
            "completed_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._records.insert(0, record)   # 最新记录在最前
        self._save()

    def get_records(self) -> List[Dict[str, Any]]:
        return self._records

    def filter_by_status(self, status: str) -> List[Dict[str, Any]]:
        if status == "全部":
            return self._records
        return [r for r in self._records if r.get("status") == status]

    def remove_record(self, record_id: int):
        self._records = [r for r in self._records if r.get("id") != record_id]
        self._save()

    def clear_all(self):
        self._records = []
        self._save()


# 全局单例
history_mgr = HistoryManager()


class HistoryPage(QWidget):
    """下载历史页面"""
    record_double_clicked = Signal(dict)  # 双击一行时发出，可用于重新下载

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_filter = "全部"
        self._history_mgr = history_mgr
        self._history_mgr._save()  # 确保文件已初始化
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 标题栏
        header = QHBoxLayout()
        self._title_label = SubtitleLabel("下载历史")
        header.addWidget(self._title_label)

        # 统计标签
        self._count_label = CaptionLabel("")
        header.addWidget(self._count_label)
        header.addStretch()

        # 清空历史按钮
        self.clear_btn = ToolButton(FIF.BROOM)
        self.clear_btn.setFixedSize(36, 36)
        self.clear_btn.setToolTip("清空全部历史")
        self.clear_btn.clicked.connect(self._on_clear_all)
        header.addWidget(self.clear_btn)

        layout.addLayout(header)

        # 筛选按钮组 + 操作按钮
        filter_layout = QHBoxLayout()
        self.filter_all = PushButton(tr("全部"))
        self.filter_success = PushButton(tr("下载完成"))
        self.filter_failed = PushButton(tr("下载失败"))
        self.filter_all.setChecked(True)

        self.filter_all.clicked.connect(lambda: self._set_filter("全部"))
        self.filter_success.clicked.connect(lambda: self._set_filter("下载完成"))
        self.filter_failed.clicked.connect(lambda: self._set_filter("下载失败"))

        filter_layout.addWidget(self.filter_all)
        filter_layout.addWidget(self.filter_success)
        filter_layout.addWidget(self.filter_failed)
        filter_layout.addStretch()

        self.redownload_btn = PushButton(FIF.DOWNLOAD, tr("重新下载"))
        self.redownload_btn.setFixedHeight(32)
        self.redownload_btn.clicked.connect(self._on_redownload)

        self.delete_btn = PushButton(FIF.DELETE, tr("删除记录"))
        self.delete_btn.setFixedHeight(32)
        self.delete_btn.clicked.connect(self._on_delete_selected)

        self.open_btn = PrimaryPushButton(FIF.FOLDER, tr("打开位置"))
        self.open_btn.setFixedHeight(32)
        self.open_btn.clicked.connect(self._on_open_location)

        filter_layout.addWidget(self.redownload_btn)
        filter_layout.addWidget(self.delete_btn)
        filter_layout.addWidget(self.open_btn)
        layout.addLayout(filter_layout)

        # 表格
        self.table = TableWidget()
        self.table.setBorderRadius(8)
        self.table.setBorderVisible(True)
        self.table.setColumnCount(len(HIST_COLUMNS))
        self.table.setHorizontalHeaderLabels(HIST_COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setItemDelegateForColumn(HIST_STATUS, HistoryDelegate(self.table))
        self.table.itemDoubleClicked.connect(self._on_row_double_clicked)

        # 列宽
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(HIST_IDX, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(HIST_NAME, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(HIST_REPO_ID, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(HIST_SOURCE, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(HIST_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(HIST_SIZE, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(HIST_TIME, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(HIST_PATH, QHeaderView.ResizeMode.Interactive)

        self.table.setColumnWidth(HIST_IDX, 45)
        self.table.setColumnWidth(HIST_REPO_ID, 160)
        self.table.setColumnWidth(HIST_SOURCE, 90)
        self.table.setColumnWidth(HIST_STATUS, 90)
        self.table.setColumnWidth(HIST_SIZE, 85)
        self.table.setColumnWidth(HIST_TIME, 150)
        self.table.setColumnWidth(HIST_PATH, 200)

        layout.addWidget(self.table, 1)

        # 填充数据
        self._refresh_table()

    def retranslateUi(self):
        self._title_label.setText(tr("下载历史"))
        self.filter_all.setText(tr("全部"))
        self.filter_success.setText(tr("完成"))
        self.filter_failed.setText(tr("失败"))
        self.open_btn.setText(tr("打开位置"))
        self.redownload_btn.setText(tr("重新下载"))
        self.delete_btn.setText(tr("删除记录"))
        self.clear_btn.setToolTip(tr("清空全部历史"))
        # 刷新表头
        col_labels = [tr("序号"), tr("文件名"), tr("模型ID"), tr("来源"),
                      tr("状态"), tr("大小"), tr("完成时间"), tr("保存路径")]
        self.table.setHorizontalHeaderLabels(col_labels)
        self._refresh_table()

    def _set_filter(self, status: str):
        self._current_filter = status
        self._refresh_table()

    def _refresh_table(self):
        records = self._history_mgr.filter_by_status(self._current_filter)
        self.table.setRowCount(0)
        self.table.setRowCount(len(records))

        # 更新统计
        all_records = self._history_mgr.get_records()
        total = len(all_records)
        success = len([r for r in all_records if r.get("status") == "下载完成"])
        failed = len([r for r in all_records if r.get("status") in ("下载失败", "已取消")])
        self._count_label.setText(
            f"{tr('全部')} {total} | {tr('完成')} {success} | {tr('失败')} {failed}"
        )

        for row, rec in enumerate(records):
            self._set_cell(row, HIST_IDX, str(row + 1))
            self._set_cell(row, HIST_NAME, rec.get("file_name", "-"))
            self._set_cell(row, HIST_REPO_ID, rec.get("repo_id", "-"))
            source = rec.get("provider", "")
            self._set_cell(row, HIST_SOURCE,
                           "HuggingFace" if source == "huggingface" else "ModelScope")
            self._set_cell(row, HIST_STATUS, rec.get("status", "-"))
            self._set_cell(row, HIST_SIZE, format_size(rec.get("file_size", -1)))
            self._set_cell(row, HIST_TIME, rec.get("completed_time", "-"))
            self._set_cell(row, HIST_PATH, rec.get("save_path", "-"))

            # 隐藏 id 列（用 role 存储）
            id_item = self.table.item(row, HIST_IDX)
            if id_item:
                id_item.setData(Qt.ItemDataRole.UserRole, rec.get("id"))

        self.table.resizeRowsToContents()

    def _set_cell(self, row: int, col: int, text: str):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if col == HIST_NAME:
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if col == HIST_PATH:
            item.setToolTip(text)
        self.table.setItem(row, col, item)

    def _get_selected_records(self):
        records = []
        for row in self.table.selectionModel().selectedRows():
            r = row.row()
            id_item = self.table.item(r, HIST_IDX)
            if id_item:
                rid = id_item.data(Qt.ItemDataRole.UserRole)
                for rec in self._history_mgr.get_records():
                    if rec.get("id") == rid:
                        records.append(rec)
                        break
        return records

    def _on_row_double_clicked(self, item: QTableWidgetItem):
        """双击行时重新下载"""
        row = item.row()
        id_item = self.table.item(row, HIST_IDX)
        if not id_item:
            return
        rid = id_item.data(Qt.ItemDataRole.UserRole)
        for rec in self._history_mgr.get_records():
            if rec.get("id") == rid:
                self.record_double_clicked.emit(rec)
                break

    def _on_open_location(self):
        records = self._get_selected_records()
        if not records:
            InfoBar.warning(
                title="提示", content="请先选择一条历史记录",
                orient=Qt.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP_RIGHT, duration=3000, parent=self
            )
            return
        opened = 0
        for rec in records:
            path = rec.get("save_path", "")
            if path and os.path.exists(path):
                os.startfile(os.path.dirname(path))
                opened += 1
            elif path:
                # 文件不存在，尝试打开上级目录
                folder = os.path.dirname(path)
                if os.path.exists(os.path.dirname(folder)):
                    os.startfile(folder)
                    opened += 1
        if opened == 0:
            InfoBar.warning(
                title="提示", content="文件路径不存在",
                orient=Qt.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP_RIGHT, duration=3000, parent=self
            )

    def _on_redownload(self):
        records = self._get_selected_records()
        if not records:
            InfoBar.warning(
                title="提示", content="请先选择要重新下载的记录",
                orient=Qt.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP_RIGHT, duration=3000, parent=self
            )
            return
        for rec in records:
            self.record_double_clicked.emit(rec)
        InfoBar.success(
            title="已添加", content=f"已将 {len(records)} 个文件添加到下载队列",
            orient=Qt.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP_RIGHT, duration=3000, parent=self
        )

    def _on_delete_selected(self):
        records = self._get_selected_records()
        if not records:
            InfoBar.warning(
                title="提示", content="请先选择要删除的记录",
                orient=Qt.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP_RIGHT, duration=3000, parent=self
            )
            return
        dialog = MessageDialog(
            title="确认删除",
            content=f"确定要删除选中的 {len(records)} 条历史记录吗？",
            parent=self
        )
        dialog.yesButton.clicked.connect(lambda: self._do_delete(records))
        dialog.cancelButton.clicked.connect(dialog.close)
        dialog.exec()

    def _do_delete(self, records):
        for rec in records:
            self._history_mgr.remove_record(rec.get("id"))
        self._refresh_table()

    def _on_clear_all(self):
        if not self._history_mgr.get_records():
            InfoBar.warning(
                title="提示", content="暂无历史记录",
                orient=Qt.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP_RIGHT, duration=3000, parent=self
            )
            return
        dialog = MessageDialog(
            title="清空历史",
            content="确定要清空全部下载历史吗？此操作不可恢复。",
            parent=self
        )
        dialog.yesButton.clicked.connect(lambda: self._do_clear_all())
        dialog.cancelButton.clicked.connect(dialog.close)
        dialog.exec()

    def _do_clear_all(self):
        self._history_mgr.clear_all()
        self._refresh_table()
