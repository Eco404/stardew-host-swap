from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

from PySide6.QtCore import Qt, QTranslator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .models import SwapOptions
from .parsing import find_farmhands, parse_root
from .paths import resolve_paths
from .reporting import generate_report
from .service import perform_swap, restore_backups
from .utils import text


class DictTranslator(QTranslator):
    def __init__(self, mapping: dict[tuple[str, str], str]) -> None:
        super().__init__()
        self.mapping = mapping

    def translate(self, context, sourceText, disambiguation=None, n: int = -1):
        return self.mapping.get((context, sourceText), sourceText)


EN_MAP: dict[tuple[str, str], str] = {
    ("MainWindow", "Stardew Host Swap"): "Stardew Host Swap",
    ("MainWindow", "导入存档文件夹"): "Import Save Folder",
    ("MainWindow", "未导入存档"): "No save loaded",
    ("MainWindow", "存档信息"): "Save Information",
    ("MainWindow", "主机：-"): "Host: -",
    ("MainWindow", "主机ID：-"): "Host ID: -",
    ("MainWindow", "提示：导入存档后会在下方列出可交换的客机角色。"): "Tip: after loading a save, available farmhands will appear below.",
    ("MainWindow", "客机角色列表"): "Farmhand List",
    ("MainWindow", "功能选项"): "Options",
    ("MainWindow", "基础信息交换"): "Basic swap",
    ("MainWindow", "homeLocation 修复"): "Fix homeLocation",
    ("MainWindow", "farmhandReference 修复"): "Fix farmhandReference",
    ("MainWindow", "房屋内部修复"): "Fix house interior",
    ("MainWindow", "mailReceived 修复"): "Fix mailReceived",
    ("MainWindow", "userID 修复"): "Fix userID",
    ("MainWindow", "SaveGameInfo 同步"): "Sync SaveGameInfo",
    ("MainWindow", "存档数据显示与结果输出"): "Save Data / Output",
    ("MainWindow", "导入存档后，这里会显示玩家信息、预检查报告、执行结果和提示信息。"): "After loading a save, this area shows player info, reports, results, and hints.",
    ("MainWindow", "刷新角色列表"): "Refresh",
    ("MainWindow", "预检查"): "Preview",
    ("MainWindow", "执行交换"): "Execute Swap",
    ("MainWindow", "恢复备份"): "Restore Backup",
    ("MainWindow", "选择存档文件夹"): "Choose save folder",
    ("MainWindow", "导入失败"): "Load failed",
    ("MainWindow", "预检查失败"): "Preview failed",
    ("MainWindow", "执行失败"): "Swap failed",
    ("MainWindow", "恢复失败"): "Restore failed",
    ("MainWindow", "恢复完成"): "Restore complete",
    ("MainWindow", "备份已恢复，原文件已回滚到 _bak 版本，备份文件已删除。"): "Backup restored. Original files were rolled back to the _bak version, and backup files were removed.",
    ("MainWindow", "未选择角色"): "No character selected",
    ("MainWindow", "请先在左侧列表中选择一个客机角色。"): "Please select a farmhand from the list first.",
    ("MainWindow", "未实现功能提示"): "Not implemented",
    ("MainWindow", "“房屋内部修复”当前仅为占位菜单，勾选它不会执行实际修复。\n\n是否仍然继续？"): "The 'Fix house interior' option is currently only a placeholder and has no actual effect.\n\nContinue anyway?",
    ("MainWindow", "执行完成"): "Done",
    ("MainWindow", "交换已完成，原文件已原地修改，并生成了 _bak 备份。"): "Swap finished. Original files were modified in place and _bak backups were created.",
    ("MainWindow", "已导入存档文件夹："): "Loaded save folder: ",
    ("MainWindow", "主机："): "Host: ",
    ("MainWindow", "检测到客机角色数量："): "Detected farmhands: ",
    ("MainWindow", "提示：房屋内部修复当前只是占位选项，尚未实现。"): "Hint: house interior fix is currently only a placeholder and not implemented.",
    ("MainWindow", "[错误] 导入失败："): "[Error] Load failed: ",
    ("MainWindow", "[错误] 预检查失败："): "[Error] Preview failed: ",
    ("MainWindow", "[错误] 执行失败："): "[Error] Swap failed: ",
    ("MainWindow", "[错误] 恢复失败："): "[Error] Restore failed: ",
    ("MainWindow", "确认恢复"): "Confirm Restore",
    ("MainWindow", "这会用 *_bak 备份覆盖当前存档文件。\n\n是否继续？"): "This will overwrite current save files with *_bak backups.\n\nContinue?",
    ("MainWindow", "确认执行交换"): "Confirm Swap",
    ("MainWindow", "这会直接修改当前存档文件，并创建 *_bak 备份。\n\n是否继续？"): "This will modify the current save files in place and create *_bak backups.\n\nContinue?",
    ("MainWindow", "切换语言"): "Switch Language",
    ("MainWindow", "名称"): "Name",
    ("MainWindow", "ID"): "ID",
}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.current_folder: Path | None = None
        self.current_resolved = None
        self.current_lang = "zh"
        self.translator = DictTranslator(EN_MAP)
        self.setAcceptDrops(True)
        self._build_ui()
        self._apply_style()
        self.retranslate_ui()

    def trctx(self, value: str) -> str:
        return QApplication.translate("MainWindow", value)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        top_bar = QHBoxLayout()
        self.import_btn = QPushButton()
        self.import_btn.clicked.connect(self.choose_folder)

        self.path_label = QLabel()
        self.path_label.setObjectName("PathLabel")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.lang_btn = QToolButton()
        self.lang_btn.setObjectName("LangButton")
        self.lang_btn.clicked.connect(self.toggle_language)
        self.lang_btn.setToolTip("Language")

        top_bar.addWidget(self.import_btn, 0)
        top_bar.addWidget(self.path_label, 1)
        top_bar.addWidget(self.lang_btn, 0, Qt.AlignRight)
        root.addLayout(top_bar)

        content = QHBoxLayout()
        content.setSpacing(14)
        root.addLayout(content, 1)

        left_col = QVBoxLayout()
        left_col.setSpacing(14)
        content.addLayout(left_col, 0)

        self.info_group = QGroupBox()
        info_layout = QVBoxLayout(self.info_group)
        self.host_label = QLabel()
        self.host_id_label = QLabel()
        self.tip_label = QLabel()
        self.tip_label.setWordWrap(True)
        info_layout.addWidget(self.host_label)
        info_layout.addWidget(self.host_id_label)
        info_layout.addWidget(self.tip_label)
        left_col.addWidget(self.info_group)

        self.players_group = QGroupBox()
        players_layout = QVBoxLayout(self.players_group)
        self.player_list = QTreeWidget()
        self.player_list.setRootIsDecorated(False)
        self.player_list.setItemsExpandable(False)
        self.player_list.itemSelectionChanged.connect(self._update_button_state)
        self.player_list.header().setStretchLastSection(True)
        self.player_list.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.player_list.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        players_layout.addWidget(self.player_list)
        left_col.addWidget(self.players_group, 1)

        self.options_group = QGroupBox()
        options_layout = QGridLayout(self.options_group)

        self.cb_basic = QCheckBox()
        self.cb_basic.setChecked(True)
        self.cb_basic.setEnabled(False)

        self.cb_home = QCheckBox()
        self.cb_home.setChecked(True)

        self.cb_farmref = QCheckBox()
        self.cb_farmref.setChecked(True)

        self.cb_interior = QCheckBox()
        self.cb_interior.setChecked(False)
        self.cb_interior.setEnabled(False)

        self.cb_mail = QCheckBox()
        self.cb_mail.setChecked(True)

        self.cb_user = QCheckBox()
        self.cb_user.setChecked(True)

        self.cb_saveinfo = QCheckBox()
        self.cb_saveinfo.setChecked(True)

        boxes = [
            self.cb_basic,
            self.cb_home,
            self.cb_farmref,
            self.cb_interior,
            self.cb_mail,
            self.cb_user,
            self.cb_saveinfo,
        ]
        for i, box in enumerate(boxes):
            options_layout.addWidget(box, i // 2, i % 2)
        left_col.addWidget(self.options_group)

        right_col = QVBoxLayout()
        right_col.setSpacing(14)
        content.addLayout(right_col, 1)

        self.log_group = QGroupBox()
        log_layout = QVBoxLayout(self.log_group)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        log_layout.addWidget(self.output_text)
        right_col.addWidget(self.log_group, 1)

        bottom_bar = QHBoxLayout()
        self.restore_btn = QPushButton()
        self.refresh_btn = QPushButton()
        self.report_btn = QPushButton()
        self.swap_btn = QPushButton()

        self.restore_btn.clicked.connect(self.run_restore)
        self.refresh_btn.clicked.connect(self.reload_current_folder)
        self.report_btn.clicked.connect(self.run_report)
        self.swap_btn.clicked.connect(self.run_swap)

        bottom_bar.addWidget(self.restore_btn)
        bottom_bar.addStretch(1)
        bottom_bar.addWidget(self.refresh_btn)
        bottom_bar.addWidget(self.report_btn)
        bottom_bar.addWidget(self.swap_btn)
        right_col.addLayout(bottom_bar)

        self._update_button_state()

    def toggle_language(self) -> None:
        self.set_language("en" if self.current_lang == "zh" else "zh")

    def set_language(self, lang: str) -> None:
        app = QApplication.instance()
        if app is None:
            return
        if self.current_lang == "en" and lang == "zh":
            app.removeTranslator(self.translator)
        elif self.current_lang == "zh" and lang == "en":
            app.installTranslator(self.translator)
        self.current_lang = lang
        self.retranslate_ui()
        self._refresh_dynamic_labels()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.trctx("Stardew Host Swap"))
        self.import_btn.setText(self.trctx("导入存档文件夹"))
        self.lang_btn.setText("🌐")
        self.lang_btn.setToolTip(self.trctx("切换语言"))

        self.info_group.setTitle(self.trctx("存档信息"))
        self.players_group.setTitle(self.trctx("客机角色列表"))
        self.options_group.setTitle(self.trctx("功能选项"))
        self.log_group.setTitle(self.trctx("存档数据显示与结果输出"))

        self.cb_basic.setText(self.trctx("基础信息交换"))
        self.cb_home.setText(self.trctx("homeLocation 修复"))
        self.cb_farmref.setText(self.trctx("farmhandReference 修复"))
        self.cb_interior.setText(self.trctx("房屋内部修复"))
        self.cb_mail.setText(self.trctx("mailReceived 修复"))
        self.cb_user.setText(self.trctx("userID 修复"))
        self.cb_saveinfo.setText(self.trctx("SaveGameInfo 同步"))

        self.output_text.setPlaceholderText(
            self.trctx("导入存档后，这里会显示玩家信息、预检查报告、执行结果和提示信息。")
        )

        self.restore_btn.setText(self.trctx("恢复备份"))
        self.refresh_btn.setText(self.trctx("刷新角色列表"))
        self.report_btn.setText(self.trctx("预检查"))
        self.swap_btn.setText(self.trctx("执行交换"))

        self.player_list.setHeaderLabels([self.trctx("名称"), self.trctx("ID")])

        if self.current_folder is None:
            self.path_label.setText(self.trctx("未导入存档"))
            self.host_label.setText(self.trctx("主机：-"))
            self.host_id_label.setText(self.trctx("主机ID：-"))
            self.tip_label.setText(self.trctx("提示：导入存档后会在下方列出可交换的客机角色。"))

    def _refresh_dynamic_labels(self) -> None:
        if self.current_resolved is None:
            return
        try:
            root = parse_root(self.current_resolved.main_save_in)
            player = root.find("player")
            self.path_label.setText(str(self.current_folder))
            self.host_label.setText(f"{self.trctx('主机：')}{text(player.find('name')) or '-'}")
            self.host_id_label.setText(
                f"{self.trctx('主机ID：-').replace('-', '').strip()} {text(player.find('UniqueMultiplayerID')) or '-'}"
            )
            self.tip_label.setText(self.trctx("提示：导入存档后会在下方列出可交换的客机角色。"))
            self.player_list.setHeaderLabels([self.trctx("名称"), self.trctx("ID")])
        except Exception:
            pass

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #0f172a;
                color: #e5e7eb;
                font-size: 14px;
            }
            QGroupBox {
                border: 1px solid #243041;
                border-radius: 16px;
                margin-top: 10px;
                padding: 12px;
                background: #111827;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #c7d2fe;
            }
            QPushButton {
                background: #2563eb;
                border: none;
                border-radius: 10px;
                padding: 10px 16px;
                font-weight: 600;
                min-height: 18px;
            }
            QPushButton:hover { background: #3b82f6; }
            QPushButton:disabled {
                background: #334155;
                color: #94a3b8;
            }
            QToolButton#LangButton {
                background: #111827;
                border: 1px solid #243041;
                border-radius: 18px;
                min-width: 36px;
                max-width: 36px;
                min-height: 36px;
                max-height: 36px;
                font-size: 16px;
            }
            QToolButton#LangButton:hover {
                background: #1f2937;
                border: 1px solid #3b82f6;
            }
            QTextEdit, QTreeWidget {
                background: #0b1220;
                border: 1px solid #243041;
                border-radius: 12px;
                padding: 8px;
            }
            QTreeWidget::item {
                padding: 8px;
                margin: 2px 0;
            }
            QTreeWidget::item:selected {
                background: #1d4ed8;
            }
            QHeaderView::section {
                background: #111827;
                color: #cbd5e1;
                border: none;
                border-bottom: 1px solid #243041;
                padding: 8px;
                font-weight: 600;
            }
            QCheckBox {
                spacing: 8px;
                padding: 4px 0;
            }
            QLabel#PathLabel {
                background: #111827;
                border: 1px solid #243041;
                border-radius: 10px;
                padding: 10px 12px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 12px;
                margin: 4px 2px 4px 2px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                min-height: 36px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: #64748b;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: transparent;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 12px;
                margin: 2px 4px 2px 4px;
            }
            QScrollBar::handle:horizontal {
                background: #475569;
                min-width: 36px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #64748b;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                background: transparent;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
            """
        )

    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            p = Path(urls[0].toLocalFile())
            if p.is_dir() or p.exists():
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if not urls:
            return
        p = Path(urls[0].toLocalFile())
        if p.is_file():
            p = p.parent
        self.load_folder(str(p))

    def _append(self, msg: str) -> None:
        self.output_text.append(msg)
        self.output_text.verticalScrollBar().setValue(
            self.output_text.verticalScrollBar().maximum()
        )

    def _clear_output(self) -> None:
        self.output_text.clear()

    def _selected_target(self):
        item = self.player_list.currentItem()
        if item is None:
            return None, None
        return item.data(0, Qt.UserRole), item.data(0, Qt.UserRole + 1)

    def _options(self) -> SwapOptions:
        return SwapOptions(
            basic_swap=True,
            fix_home_location=self.cb_home.isChecked(),
            fix_farmhand_reference=self.cb_farmref.isChecked(),
            fix_house_interior=self.cb_interior.isChecked(),
            fix_mail_received=self.cb_mail.isChecked(),
            fix_user_id=self.cb_user.isChecked(),
            sync_savegameinfo=self.cb_saveinfo.isChecked(),
        )

    def _update_button_state(self) -> None:
        ready = self.current_folder is not None
        has_target = self.player_list.currentItem() is not None
        self.restore_btn.setEnabled(ready)
        self.refresh_btn.setEnabled(ready)
        self.report_btn.setEnabled(ready and has_target)
        self.swap_btn.setEnabled(ready and has_target)

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self.trctx("选择存档文件夹"))
        if folder:
            self.load_folder(folder)

    def reload_current_folder(self) -> None:
        if self.current_folder is not None:
            self.load_folder(str(self.current_folder))

    def load_folder(self, folder: str) -> None:
        try:
            path = Path(folder)
            if not path.exists():
                raise FileNotFoundError("Path does not exist.")
            if path.is_file():
                path = path.parent

            resolved = resolve_paths(path, output_main=None, report=False)
            root = parse_root(resolved.main_save_in)
            player = root.find("player")
            if player is None:
                raise ValueError("Host player node not found.")

            self.current_folder = path
            self.current_resolved = resolved
            self.path_label.setText(str(path))
            self.host_label.setText(f"{self.trctx('主机：')}{text(player.find('name')) or '-'}")
            self.host_id_label.setText(
                f"{self.trctx('主机ID：-').replace('-', '').strip()} {text(player.find('UniqueMultiplayerID')) or '-'}"
            )
            self.tip_label.setText(self.trctx("提示：导入存档后会在下方列出可交换的客机角色。"))

            self.player_list.clear()
            self.player_list.setHeaderLabels([self.trctx("名称"), self.trctx("ID")])

            for idx, fh in enumerate(find_farmhands(root)):
                name = text(fh.find("name")) or "(empty)"
                mpid = text(fh.find("UniqueMultiplayerID"))
                home = text(fh.find("homeLocation"))

                item = QTreeWidgetItem([name, mpid])
                tooltip = f"Index: {idx}\nName: {name}\nID: {mpid}\nHome: {home}"
                item.setToolTip(0, tooltip)
                item.setToolTip(1, tooltip)
                item.setData(0, Qt.UserRole, name)
                item.setData(0, Qt.UserRole + 1, mpid)
                self.player_list.addTopLevelItem(item)

            self._clear_output()
            self._append(f"{self.trctx('已导入存档文件夹：')}{path}")
            self._append(f"{self.trctx('主机：')}{text(player.find('name'))}  |  ID: {text(player.find('UniqueMultiplayerID'))}")
            self._append(f"{self.trctx('检测到客机角色数量：')}{self.player_list.topLevelItemCount()}")
            if self.cb_interior.isChecked():
                self._append(self.trctx("提示：房屋内部修复当前只是占位选项，尚未实现。"))
        except Exception as exc:
            QMessageBox.critical(self, self.trctx("导入失败"), str(exc))
            self._append(f"{self.trctx('[错误] 导入失败：')}{exc}")
        finally:
            self._update_button_state()

    def run_report(self) -> None:
        if self.current_resolved is None:
            return

        target_name, target_id = self._selected_target()
        if not target_name and not target_id:
            QMessageBox.warning(
                self,
                self.trctx("未选择角色"),
                self.trctx("请先在左侧列表中选择一个客机角色。"),
            )
            return

        try:
            report = generate_report(
                self.current_resolved.main_save_in,
                target_name=target_name,
                target_id=target_id,
                resolved=self.current_resolved,
                options=self._options(),
            )
            self._clear_output()
            self._append(report)
        except Exception as exc:
            QMessageBox.critical(self, self.trctx("预检查失败"), str(exc))
            self._append(f"{self.trctx('[错误] 预检查失败：')}{exc}")

    def run_swap(self) -> None:
        if self.current_resolved is None:
            return

        target_name, target_id = self._selected_target()
        if not target_name and not target_id:
            QMessageBox.warning(
                self,
                self.trctx("未选择角色"),
                self.trctx("请先在左侧列表中选择一个客机角色。"),
            )
            return

        ret = QMessageBox.question(
            self,
            self.trctx("确认执行交换"),
            self.trctx("这会直接修改当前存档文件，并先创建 *_bak 备份。\n\n是否继续？"),
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        if self.cb_interior.isChecked():
            ret = QMessageBox.question(
                self,
                self.trctx("未实现功能提示"),
                self.trctx("“房屋内部修复”当前仅为占位菜单，勾选它不会执行实际修复。\n\n是否仍然继续？"),
            )
            if ret != QMessageBox.StandardButton.Yes:
                return

        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                perform_swap(
                    self.current_resolved.main_save_in,
                    self.current_resolved.output_main,
                    target_name=target_name,
                    target_id=target_id,
                    savegameinfo_in=self.current_resolved.savegameinfo_in,
                    output_savegameinfo=self.current_resolved.output_savegameinfo,
                    options=self._options(),
                )
            self._clear_output()
            self._append(buf.getvalue().strip())
            QMessageBox.information(
                self,
                self.trctx("执行完成"),
                self.trctx("交换已完成，原文件已原地修改，并生成了 _bak 备份。"),
            )
            self.reload_current_folder()
        except Exception as exc:
            QMessageBox.critical(self, self.trctx("执行失败"), str(exc))
            self._append(f"{self.trctx('[错误] 执行失败：')}{exc}")

    def run_restore(self) -> None:
        if self.current_resolved is None:
            return

        ret = QMessageBox.question(
            self,
            self.trctx("确认恢复"),
            self.trctx("这会用 *_bak 备份覆盖当前存档文件。\n\n是否继续？"),
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        try:
            restore_backups(
                self.current_resolved.main_save_in,
                self.current_resolved.savegameinfo_in if self.cb_saveinfo.isChecked() else None,
            )
            self._clear_output()
            self._append(self.trctx("备份已恢复，原文件已回滚到 _bak 版本，备份文件已删除。"))
            QMessageBox.information(
                self,
                self.trctx("恢复完成"),
                self.trctx("备份已恢复，原文件已回滚到 _bak 版本，备份文件已删除。"),
            )
            self.reload_current_folder()
        except Exception as exc:
            QMessageBox.critical(self, self.trctx("恢复失败"), str(exc))
            self._append(f"{self.trctx('[错误] 恢复失败：')}{exc}")


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Stardew Host Swap")
    window = MainWindow()
    window.resize(1180, 760)
    window.show()
    return app.exec()