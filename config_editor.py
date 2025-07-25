# config_editor.py
from PySide6.QtWidgets import QWidget, QFormLayout, QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout, QMessageBox
from PySide6.QtCore import Qt
import ast
from config_loader import _load_config_file
from constants import DEFAULT_CONFIG_FILE, ADVANCED_CONFIG_FILE, MANDATORY_CONFIG_KEYS

class ConfigEditor(QWidget):
    def __init__(self, personal_config_path=None, default_config_path=DEFAULT_CONFIG_FILE):
        super().__init__()
        self.personal_config_path = personal_config_path
        self.default_config = _load_config_file(default_config_path)
        self.initial_personal_config = _load_config_file(personal_config_path) # Store initial for clear
        self.personal_config = self.initial_personal_config.copy()
        self.merged_config = {**self.default_config, **self.personal_config}
        self.fields = {}
        self.build_ui()
        self.is_modified = False
        self.update_save_button_state()

    def build_ui(self):
        self.layout = QVBoxLayout()
        self.form = QFormLayout()
        self.setLayout(self.layout)

        if self.personal_config_path:
            # Display personal config fields first
            for key, value in self.personal_config.items():
                field = QLineEdit(str(value))
                self.fields[key] = field
                self.form.addRow(key, field)
                field.textChanged.connect(self.set_modified)

        # Display default config fields if not in personal config
        for key, value in self.default_config.items():
            if key not in self.personal_config:
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

        self.save_button.clicked.connect(self._save_config_to_file)
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

    def _save_config_to_file(self):
        current_config = self.get_config()
        missing_fields = [field for field in MANDATORY_CONFIG_KEYS if not current_config.get(field)]

        if missing_fields:
            reply = QMessageBox.warning(
                self,
                "Missing Mandatory Fields",
                f"The following mandatory fields are empty: {', '.join(missing_fields)}.\n\nDo you want to save anyway?",
                QMessageBox.Save | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Config File", self.personal_config_path, "Python Files (*.py)"
        )
        if not path:
            return

        modified_config = {}
        for key, value in current_config.items():
            if key not in self.default_config or self.default_config[key] != value:
                modified_config[key] = value

        with open(path, "w") as f:
            for k, v in modified_config.items():
                f.write(f'{k} = {repr(v)}\n')
        self.is_modified = False
        self.update_save_button_state()
        QMessageBox.information(self, "Save Complete", f"Configuration saved to {path}")

    def clear_changes(self):
        for key, field in self.fields.items():
            if key in self.initial_personal_config:
                field.setText(str(self.initial_personal_config[key]))
            elif key in self.default_config:
                field.setText(str(self.default_config[key]))
            else:
                field.setText("") # Clear fields that were added and are not in default/initial personal
        self.is_modified = False
        self.update_save_button_state()
