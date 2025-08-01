import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QWidget,
    QVBoxLayout, QHBoxLayout, QTextEdit, QScrollArea, QSplitter
)
from PySide6.QtCore import Qt
from controller import Controller

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

        button_style = "QPushButton { font-size: 14px; padding: 5px; }"
        self.home_button = QPushButton("🏠 Home")
        self.home_button.setStyleSheet(button_style)
        self.create_button = QPushButton("➕ Create Config")
        self.create_button.setStyleSheet(button_style)
        self.load_button = QPushButton("📂 Load Config")
        self.load_button.setStyleSheet(button_style)
        self.run_button = QPushButton("▶ Run OpenRAM")
        self.run_button.setStyleSheet(button_style)
        self.view_button = QPushButton("📄 View Output")
        self.view_button.setStyleSheet(button_style)
        self.advanced_settings_button = QPushButton("⚙️ Advanced Settings")
        self.advanced_settings_button.setStyleSheet(button_style)

        self.sidebar.addWidget(self.home_button)
        self.sidebar.addWidget(self.create_button)
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
        
        self.controller = Controller(self) # Initialize controller here
        
        # Connect signals to controller slots
        self.home_button.clicked.connect(self.controller.show_home_screen)
        self.create_button.clicked.connect(self.controller.create_new_config)
        self.load_button.clicked.connect(self.controller.load_config)
        self.run_button.clicked.connect(self.controller.run_openram)
        self.view_button.clicked.connect(self.controller.view_output)
        self.advanced_settings_button.clicked.connect(self.controller.show_advanced_settings)

        self.controller.show_home_screen() # Show home screen on startup
