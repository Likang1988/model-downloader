import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QCheckBox, QPushButton, QHeaderView, QWidget, QAbstractItemView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from qfluentwidgets import PrimaryPushButton, PushButton, BodyLabel, CaptionLabel
from .downloader import FileInfo
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


class FileTreeDialog(QDialog):
    """树形文件选择对话框 - 带文件夹结构、图标、复选框"""

    def __init__(self, files: list, parent=None):
        super().__init__(parent)
        self.files = files
        self._selected_files = []
        self.setWindowTitle(tr("选择要下载的文件"))
        self.resize(700, 550)
        self.init_ui()
        self.populate_tree()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # 顶部信息栏
        info_layout = QHBoxLayout()
        self.repo_label = BodyLabel(tr("共 {0} 个文件").format(len(self.files)))
        info_layout.addWidget(self.repo_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 工具栏
        toolbar = QHBoxLayout()
        self.select_all_cb = QCheckBox(tr("全选"))
        self.select_all_cb.toggled.connect(self.on_select_all_toggled)
        self.expand_btn = QPushButton(tr("展开全部"))
        self.expand_btn.clicked.connect(self.toggle_expand)
        self.collapse_btn = QPushButton(tr("折叠全部"))
        self.collapse_btn.clicked.connect(self.collapse_all)

        self.selection_label = CaptionLabel(tr("已选择 0 项"))
        self.size_label = CaptionLabel(tr("总大小: 0 B"))

        toolbar.addWidget(self.select_all_cb)
        toolbar.addWidget(self.expand_btn)
        toolbar.addWidget(self.collapse_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.selection_label)
        toolbar.addWidget(self.size_label)
        layout.addLayout(toolbar)

        # 树形控件
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("文件名"), tr("大小"), tr("类型")])
        self.tree.setColumnWidth(0, 350)
        self.tree.setColumnWidth(1, 100)
        self.tree.setIndentation(20)
        self.tree.setAnimated(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 3px 0px;
            }
            QTreeWidget::item:hover {
                background-color: #f0f4ff;
            }
        """)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemChanged.connect(self.on_item_changed)
        layout.addWidget(self.tree, 1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.cancel_btn = PushButton(tr("取消"))
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = PrimaryPushButton(tr("加入队列 (0)"))
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setEnabled(False)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        layout.addLayout(btn_layout)

    def populate_tree(self):
        """将文件列表填充到树形控件（按路径层级分组）"""
        self.tree.blockSignals(True)

        # 先按目录结构分组
        dir_map = {}  # dir_path -> (dir_item, [child_files])
        root_items = []

        for f in self.files:
            parts = f.path.split("/")
            if len(parts) == 1:
                # 根目录文件
                item = QTreeWidgetItem()
                item.setText(0, f.name)
                item.setText(1, format_size(f.size) if f.size else "-")
                item.setText(2, self._guess_file_type(f.name))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole, f)
                item.setToolTip(0, f.path)
                root_items.append(item)
            else:
                # 有目录层级
                dir_path = "/".join(parts[:-1])
                if dir_path not in dir_map:
                    dir_map[dir_path] = []
                dir_map[dir_path].append(f)

        # 创建目录节点
        dir_items = {}
        for dir_path in sorted(dir_map.keys()):
            parts = dir_path.split("/")
            parent_item = None
            current_path = ""
            for i, part in enumerate(parts):
                current_path = current_path + "/" + part if current_path else part
                if current_path not in dir_items:
                    item = QTreeWidgetItem()
                    item.setText(0, "📁 " + part)
                    item.setText(1, "")
                    item.setText(2, "文件夹")
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.CheckState.Checked)
                    item.setData(0, Qt.ItemDataRole.UserRole, None)
                    item.setData(1, Qt.ItemDataRole.UserRole, current_path)

                    if parent_item:
                        parent_item.addChild(item)
                    else:
                        root_items.append(item)

                    dir_items[current_path] = item
                    parent_item = item
                else:
                    parent_item = dir_items[current_path]

            # 将文件添加到目录下
            dir_item = dir_items[dir_path]
            for f in dir_map[dir_path]:
                item = QTreeWidgetItem()
                item.setText(0, f.name)
                item.setText(1, format_size(f.size) if f.size else "-")
                item.setText(2, self._guess_file_type(f.name))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole, f)
                item.setToolTip(0, f.path)
                dir_item.addChild(item)

        # 添加到树
        self.tree.addTopLevelItems(root_items)
        self.tree.blockSignals(False)

        # 更新状态
        QTimer.singleShot(50, self.update_selection_info)

    def _guess_file_type(self, filename: str) -> str:
        ext = os.path.splitext(filename.lower())[1]
        mapping = {
            ".bin": "模型文件", ".safetensors": "SafeTensor模型",
            ".pt": "PyTorch模型", ".pth": "PyTorch模型", ".onnx": "ONNX模型",
            ".json": "配置文件", ".txt": "文本", ".md": "文档",
            ".py": "Python脚本", ".yaml": "YAML配置", ".yml": "YAML配置",
            ".gitattributes": "Git配置", ".gitignore": "Git配置",
            ".h5": "HDF5模型", ".pkl": "Pickle文件",
        }
        return mapping.get(ext, ext.upper() + "文件" if ext else "文件")

    def on_select_all_toggled(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.tree.blockSignals(True)
        self._set_all_states(self.tree.invisibleRootItem(), state)
        self.tree.blockSignals(False)
        self.update_selection_info()

    def _set_all_states(self, parent_item, state: Qt.CheckState):
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child.setCheckState(0, state)
            self._set_all_states(child, state)

    def on_item_changed(self, item: QTreeWidgetItem, column: int):
        if column == 0:
            # 同步子项的选中状态
            if item.childCount() > 0:
                self.tree.blockSignals(True)
                state = item.checkState(0)
                self._set_all_states(item, state)
                self.tree.blockSignals(False)
            # 更新父项状态
            self._update_parent_state(item)
            self.update_selection_info()

    def _update_parent_state(self, item):
        parent = item.parent()
        if parent is None:
            return
        checked = 0
        unchecked = 0
        for i in range(parent.childCount()):
            s = parent.child(i).checkState(0)
            if s == Qt.CheckState.Checked:
                checked += 1
            elif s == Qt.CheckState.Unchecked:
                unchecked += 1

        self.tree.blockSignals(True)
        if unchecked == 0:
            parent.setCheckState(0, Qt.CheckState.Checked)
        elif checked == 0:
            parent.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
        self.tree.blockSignals(False)

        # 递归向上
        self._update_parent_state(parent)

    def update_selection_info(self):
        selected = self.get_selected_files()
        count = len(selected)
        total_size = sum(f.size for f in selected)

        self.selection_label.setText(tr("已选择 {0} 项").format(count))
        self.size_label.setText(tr("总大小: {0}").format(format_size(total_size)))
        self.ok_btn.setText(tr("加入队列 ({0})").format(count))
        self.ok_btn.setEnabled(count > 0)

    def toggle_expand(self):
        """展开/折叠全部"""
        expanded = any(self.tree.topLevelItem(i).isExpanded()
                       for i in range(self.tree.topLevelItemCount())
                       if self.tree.topLevelItem(i).childCount() > 0)
        self._set_expand_all(self.tree.invisibleRootItem(), not expanded)

    def _set_expand_all(self, parent_item, expand: bool):
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.childCount() > 0:
                child.setExpanded(expand)
                self._set_expand_all(child, expand)

    def collapse_all(self):
        self._set_expand_all(self.tree.invisibleRootItem(), False)

    def get_selected_files(self):
        """递归获取所有选中的文件"""
        result = []
        self._collect_checked(self.tree.invisibleRootItem(), result)
        return result

    def _collect_checked(self, parent_item, result: list):
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.checkState(0) == Qt.CheckState.Checked:
                f = child.data(0, Qt.ItemDataRole.UserRole)
                if f is not None:
                    result.append(f)
            self._collect_checked(child, result)
