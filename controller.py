import os
import subprocess
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtCore import QCoreApplication
from config_loader import load_config
from config_editor import ConfigEditor

class Controller:
    def __init__(self, ui):
        self.ui = ui
        self.config = {}
        self.config_path = None

    def load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            None, "Open Config File", "", "Python Files (*.py)"
        )
        if not path:
            return

        self.config = load_config(path)
        self.config_path = path

        if self.ui.editor:
            self.ui.scroll_area.takeWidget()
            self.ui.editor.deleteLater()
            self.ui.editor = None

        self.ui.editor = ConfigEditor(self.config)
        self.ui.editor.setMinimumWidth(400)
        self.ui.scroll_area.setWidget(self.ui.editor)

    def save_config(self):
        if not self.ui.editor:
            QMessageBox.warning(None, "No Config", "Nothing to save.")
            return
        self.ui.editor.save_config()

    def run_openram(self):
        pass
        # if not self.config_path:
        #     QMessageBox.warning(None, "No Config", "Please load a config first.")
        #     return

        # self.ui.log_output.clear()
        # self.ui.log_output.append(f"Running OpenRAM with: {self.config_path}\n")

        # try:
        #     process = subprocess.Popen(
        #         ["python3", "openram.py", self.config_path],
        #         stdout=subprocess.PIPE,
        #         stderr=subprocess.STDOUT,
        #         universal_newlines=True
        #     )

        #     for line in process.stdout:
        #         self.ui.log_output.append(line)
        #         QCoreApplication.processEvents()

        #     process.wait()
        #     self.ui.log_output.append("\n✅ Finished running OpenRAM.")

        # except Exception as e:
        #     QMessageBox.critical(None, "Error", str(e))

    def view_gds(self):
        # subprocess.Popen(["klayout", "test.gds"])
        pass
