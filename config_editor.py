# config_editor.py
from PySide6.QtWidgets import QWidget, QFormLayout, QLineEdit, QPushButton, QFileDialog, QVBoxLayout
from PySide6.QtCore import Qt
import ast

class ConfigEditor(QWidget):
    def __init__(self, config_dict):
        super().__init__()
        self.config_dict = config_dict
        self.fields = {}
        self.build_ui()

    def build_ui(self):
        self.layout = QVBoxLayout()
        self.form = QFormLayout()
        self.setLayout(self.layout)

        # Generate editable fields
        for key, value in self.config_dict.items():
            field = QLineEdit(str(value))
            self.fields[key] = field
            self.form.addRow(key, field)

        self.layout.addLayout(self.form)

    def get_config(self):
        config = {}
        for key, widget in self.fields.items():
            val = widget.text()
            try:
                config[key] = ast.literal_eval(val)
            except Exception:
                config[key] = val
        return config

    def save_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Config As", "config.py", "Python Files (*.py)")
        if path:
            config = self.get_config()
            with open(path, "w") as f:
                for k, v in config.items():
                    f.write(f"{k} = {repr(v)}\n")
