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
        self.save_button = QPushButton("💾 Save Config As")
        self.run_button = QPushButton("▶ Run OpenRAM")
        self.view_button = QPushButton("🧿 View GDS")
        # self.advanced_settings_button = QPushButton("⚙️ Advanced Settings")

        self.sidebar.addWidget(self.load_button)
        self.sidebar.addWidget(self.save_button)
        self.sidebar.addWidget(self.run_button)
        self.sidebar.addWidget(self.view_button)
        # self.sidebar.addWidget(self.advanced_settings_button)
        self.sidebar.addStretch()

        # --- Right panel layout ---
        self.right_panel = QVBoxLayout()
        
        # Replace right_panel layout setup:
        self.right_splitter = QSplitter(Qt.Vertical)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(150)  # optional

        # Add both to the splitter
        self.right_splitter.addWidget(self.scroll_area)
        self.right_splitter.addWidget(self.log_output)
        self.right_splitter.setSizes([500, 50])

        # Add splitter to right panel
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
