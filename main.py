import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from ui import Ui_MainWindow
from controller import Controller

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        self.controller = Controller(self.ui)
        
        # --- Connect signals to slots ---
        self.ui.load_button.clicked.connect(self.controller.load_config)
        
        self.ui.run_button.clicked.connect(self.controller.run_openram)
        self.ui.view_button.clicked.connect(self.controller.view_gds)
        self.ui.advanced_settings_button.clicked.connect(self.controller.show_advanced_settings)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
