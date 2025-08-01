# advanced_config_editor.py
from PySide6.QtWidgets import QWidget, QFormLayout, QLineEdit, QPushButton, QVBoxLayout, QFileDialog, QHBoxLayout, QMessageBox, QComboBox
from PySide6.QtCore import Qt, QDir
import ast
import os
from config_loader import _load_config_file
from constants import ADVANCED_CONFIG_FILE, TECHNOLOGY_PATH, OPENRAM_PATH
import shutil


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
            if key == OPENRAM_PATH:
                path_layout = QHBoxLayout()
                field = QLineEdit(str(value))
                browse_button = QPushButton("Browse")
                browse_button.clicked.connect(lambda current_field=field: self.browse_openram_path(current_field))
                path_layout.addWidget(field)
                path_layout.addWidget(browse_button)
                self.fields[key] = field
                self.form.addRow(key, path_layout)
            elif key == "tech_name":
                tech_layout = QHBoxLayout()
                combo = QComboBox()

                # Construct technology folder path
                tech_base_path = os.path.join(self.config_dict.get(OPENRAM_PATH, ""), TECHNOLOGY_PATH)

                try:
                    tech_folders = [
                        name for name in os.listdir(tech_base_path)
                        if os.path.isdir(os.path.join(tech_base_path, name))
                    ]
                    combo.addItems(tech_folders)
                except Exception as e:
                    combo.addItem("Error loading tech folders")

                # Set current value if it matches one of the folders
                if str(value) in tech_folders:
                    combo.setCurrentText(str(value))

                upload_button = QPushButton("Upload Technology")
                upload_button.clicked.connect(lambda: self.upload_pdk_folder(combo, tech_base_path))

                tech_layout.addWidget(combo)
                tech_layout.addWidget(upload_button)
                self.fields[key] = combo
                self.form.addRow(key, tech_layout)

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
            
    
    def upload_pdk_folder(self, combo: QComboBox, tech_base_path: str):
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Upload",
            QDir.homePath()
        )

        if not folder_path:
            return  # User cancelled

        folder_name = os.path.basename(folder_path)
        os.makedirs(tech_base_path, exist_ok=True)
        target_path = os.path.join(tech_base_path, folder_name)

        # Auto-rename if folder exists
        if os.path.exists(target_path):
            base, i = target_path, 1
            while os.path.exists(f"{base}_{i}"):
                i += 1
            target_path = f"{base}_{i}"
            folder_name = os.path.basename(target_path)

        try:
            shutil.copytree(folder_path, target_path)
            QMessageBox.information(self, "Success", f"Folder uploaded to:\n{target_path}")

            # Refresh the combo box
            combo.clear()
            tech_folders = [
                name for name in os.listdir(tech_base_path)
                if os.path.isdir(os.path.join(tech_base_path, name))
            ]
            combo.addItems(tech_folders)
            combo.setCurrentText(folder_name)  # Select the newly uploaded folder
            self.set_modified()  # If you track unsaved changes

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to upload folder:\n{e}")