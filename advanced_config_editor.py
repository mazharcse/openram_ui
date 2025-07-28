# advanced_config_editor.py
from PySide6.QtWidgets import QWidget, QFormLayout, QLineEdit, QPushButton, QVBoxLayout, QFileDialog, QHBoxLayout, QMessageBox
from PySide6.QtCore import Qt
import ast
from config_loader import _load_config_file
from constants import ADVANCED_CONFIG_FILE

class AdvancedConfigEditor(QWidget):
    def __init__(self, config_path=ADVANCED_CONFIG_FILE):
        super().__init__()
        self.config_path = config_path
        self.initial_config_dict = _load_config_file(config_path) # Store initial for clear
        self.config_dict = self.initial_config_dict.copy()
        self.fields = {}
        self.build_ui()
        self.is_modified = False
        self.update_save_button_state()

    def build_ui(self):
        self.setWindowTitle("Advanced Settings")
        self.layout = QVBoxLayout()
        self.form = QFormLayout()
        self.setLayout(self.layout)

        # Generate editable fields
        for key, value in self.config_dict.items():
            if key == "openram_path":
                path_layout = QHBoxLayout()
                field = QLineEdit(str(value))
                browse_button = QPushButton("Browse")
                browse_button.clicked.connect(lambda current_field=field: self.browse_openram_path(current_field))
                path_layout.addWidget(field)
                path_layout.addWidget(browse_button)
                self.fields[key] = field
                self.form.addRow(key, path_layout)
            else:
                field = QLineEdit(str(value))
                self.fields[key] = field
                self.form.addRow(key, field)
            field.textChanged.connect(self.set_modified)

        self.layout.addLayout(self.form)

        # Add Save and Clear buttons
        self.button_layout = QHBoxLayout()
        self.save_button = QPushButton("💾 Save")
        self.clear_button = QPushButton("🗑️ Clear")
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.clear_button)
        self.layout.addLayout(self.button_layout)

        self.save_button.clicked.connect(self._save_config)
        self.clear_button.clicked.connect(self.clear_changes)

    def set_modified(self):
        self.is_modified = True
        self.update_save_button_state()

    def update_save_button_state(self):
        self.save_button.setEnabled(self.is_modified)

    def get_config(self):
        config = {}
        for key, widget in self.fields.items():
            val = widget.text()
            try:
                config[key] = ast.literal_eval(val)
            except Exception:
                config[key] = val
        return config

    def _save_config(self):
        config = self.get_config()
        with open(self.config_path, "w") as f:
            for k, v in config.items():
                f.write(f'''{k} = {repr(v)}
''')
        self.is_modified = False
        self.update_save_button_state()
        QMessageBox.information(self, "Save Complete", f"Advanced configuration saved to {self.config_path}")

    def clear_changes(self):
        for key, field in self.fields.items():
            if key in self.initial_config_dict:
                field.setText(str(self.initial_config_dict[key]))
            else:
                field.setText("") # Clear fields that were added and are not in initial config
        self.is_modified = False
        self.update_save_button_state()

    def browse_openram_path(self, field_widget):
        directory = QFileDialog.getExistingDirectory(self, "Select OpenRAM Directory")
        if directory:
            field_widget.setText(directory)
            self.set_modified()