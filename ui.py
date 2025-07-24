import sys
import os
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QPushButton, QWidget,
    QVBoxLayout, QHBoxLayout, QTextEdit, QMessageBox, QScrollArea, QSplitter
)
from PySide6.QtCore import Qt
from config_loader import load_config
from config_editor import ConfigEditor
from constants import MANDATORY_CONFIG_KEYS

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setWindowTitle("OpenRAM UI")
        MainWindow.resize(900, 600)

        self.central_widget = QWidget()
        MainWindow.setCentralWidget(self.central_widget)

        self.main_layout = QHBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        # --- Sidebar layout ---
        self.sidebar = QVBoxLayout()
        self.sidebar.setSpacing(10)

        self.load_button = QPushButton("📂 Load Config")
        self.run_button = QPushButton("▶ Run OpenRAM")
        self.view_button = QPushButton("🧿 View GDS")
        self.advanced_settings_button = QPushButton("⚙️ Advanced Settings")

        self.sidebar.addWidget(self.load_button)
        self.sidebar.addWidget(self.run_button)
        self.sidebar.addWidget(self.view_button)
        self.sidebar.addWidget(self.advanced_settings_button)
        self.sidebar.addStretch()

        # --- Right panel layout ---
        self.right_panel = QVBoxLayout()
        
        self.right_splitter = QSplitter(Qt.Vertical)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(150)

        self.right_splitter.addWidget(self.scroll_area)
        self.right_splitter.addWidget(self.log_output)
        self.right_splitter.setSizes([500, 50])

        self.right_panel.addWidget(self.right_splitter)

        # --- Add to main layout ---
        sidebar_widget = QWidget()
        sidebar_widget.setLayout(self.sidebar)
        sidebar_widget.setFixedWidth(200)

        right_widget = QWidget()
        right_widget.setLayout(self.right_panel)

        self.main_layout.addWidget(sidebar_widget)
        self.main_layout.addWidget(right_widget)

        self.editor = None
        self.scroll_area.setWidget(self.editor)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.config_path = None
        self.load_button.clicked.connect(self.load_config_file)
        self.run_button.clicked.connect(self.run_openram)
        self.view_button.clicked.connect(self.view_gds)
        self.advanced_settings_button.clicked.connect(self.show_advanced_settings)

    def load_config_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Config", "", "Python Files (*.py)")
        if file_path:
            self.config_path = file_path
            self.editor = ConfigEditor(self.config_path)
            self.scroll_area.setWidget(self.editor)

    def run_openram(self):
        if not self.config_path:
            QMessageBox.warning(self, "Warning", "Please load a config file first.")
            return

        # Validate mandatory fields
        current_config = self.editor.get_config()
        missing_fields = [field for field in MANDATORY_CONFIG_KEYS if not current_config.get(field)]
        if missing_fields:
            QMessageBox.critical(self, "Error", f"Missing mandatory fields: {', '.join(missing_fields)}")
            return

        self.log_output.clear()
        self.log_output.append("Running OpenRAM...")

        openram_dir = os.environ.get("OPENRAM_DIR")
        if not openram_dir:
            QMessageBox.critical(self, "Error", "OPENRAM_DIR environment variable not set.")
            return

        command = f"python3 {openram_dir}/sram_compiler.py {self.config_path}"
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        while True:
            output = process.stdout.readline().decode()
            if output == '' and process.poll() is not None:
                break
            if output:
                self.log_output.append(output.strip())
        
        rc = process.poll()
        if rc != 0:
            self.log_output.append(f"OpenRAM failed with exit code {rc}")
            self.log_output.append(process.stderr.read().decode())

    def view_gds(self):
        if not self.config_path:
            QMessageBox.warning(self, "Warning", "Please load a config file first.")
            return

        config = self.editor.get_config()
        gds_file = os.path.join(config.get("output_path"), f"{config.get('output_name')}.gds")

        if not os.path.exists(gds_file):
            QMessageBox.warning(self, "Warning", f"GDS file not found: {gds_file}")
            return

        # Use klayout to view the GDS file
        try:
            subprocess.run(["klayout", gds_file], check=True)
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "klayout not found. Please make sure it is installed and in your PATH.")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Error", f"Error opening klayout: {e}")

    def show_advanced_settings(self):
        from advanced_config_editor import AdvancedConfigEditor
        self.adv_settings_win = AdvancedConfigEditor()
        self.adv_settings_win.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())