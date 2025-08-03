# advanced_config_editor.py
from PySide6.QtWidgets import (QWidget, QFormLayout, QLineEdit, QPushButton, QVBoxLayout, 
                             QFileDialog, QHBoxLayout, QMessageBox, QListWidget)
from PySide6.QtCore import Qt, QDir
import ast
import os
from config_loader import _load_config_file
from constants import ADVANCED_CONFIG_FILE, TECHNOLOGY_PATH, OPENRAM_PATH, TECHNOLOGY_FILE
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
                browse_button.clicked.connect(lambda: self.browse_openram_path(field))
                path_layout.addWidget(field)
                path_layout.addWidget(browse_button)
                self.fields[key] = field
                self.form.addRow(key, path_layout)
                field.textChanged.connect(self.set_modified)
            elif key == "tech_name":
                tech_layout = QVBoxLayout()
                list_widget = QListWidget()
                list_widget.setSelectionMode(QListWidget.NoSelection)
                self.fields[key] = list_widget 

                self.populate_tech_list(list_widget)

                upload_button = QPushButton("Upload New Technology")
                upload_button.clicked.connect(lambda: self.upload_pdk_folder(list_widget))

                tech_layout.addWidget(list_widget)
                tech_layout.addWidget(upload_button)
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

    def populate_tech_list(self, list_widget):
        list_widget.clear()
        try:
            with open(TECHNOLOGY_FILE, "r") as f:
                techs = [line.strip() for line in f if line.strip()]
                list_widget.addItems(techs)
        except FileNotFoundError:
            QMessageBox.warning(self, "Warning", "technology file not found. Please create it.")

    def set_modified(self):
        self.is_modified = True
        self.update_save_button_state()

    def update_save_button_state(self):
        self.save_button.setEnabled(self.is_modified)

    def get_config(self):
        config = {}
        for key, widget in self.fields.items():
            if isinstance(widget, QListWidget):
                selected_items = widget.selectedItems()
                if selected_items:
                    config[key] = selected_items[0].text()
                else: # If nothing is selected, keep the initial value
                    config[key] = self.initial_config_dict.get(key, "")
            elif isinstance(widget, QLineEdit):
                val = widget.text()
                try:
                    config[key] = ast.literal_eval(val)
                except (ValueError, SyntaxError):
                    config[key] = val
        return config

    def _save_config(self):
        config = self.get_config()
        with open(self.config_path, "w") as f:
            for k, v in config.items():
                f.write(f'{k} = {repr(v)}\n')
        self.is_modified = False
        self.update_save_button_state()
        self.initial_config_dict = config # Update initial state
        QMessageBox.information(self, "Save Complete", f"Advanced configuration saved to {self.config_path}")

    def clear_changes(self):
        for key, field in self.fields.items():
            if key in self.initial_config_dict:
                initial_value = str(self.initial_config_dict[key])
                if isinstance(field, QListWidget):
                    pass
                elif isinstance(field, QLineEdit):
                    field.setText(initial_value)
            else:
                if isinstance(field, QLineEdit):
                    field.setText("")
        self.is_modified = False
        self.update_save_button_state()

    def browse_openram_path(self, field_widget):
        directory = QFileDialog.getExistingDirectory(self, "Select OpenRAM Directory")
        if directory:
            field_widget.setText(directory)
            self.set_modified()
            
    def upload_pdk_folder(self, list_widget: QListWidget):
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Upload",
            QDir.homePath()
        )

        if not folder_path:
            return  # User cancelled

        folder_name = os.path.basename(folder_path)
        
        openram_path_field = self.fields.get(OPENRAM_PATH)
        if not openram_path_field or not openram_path_field.text() or not os.path.isdir(openram_path_field.text()):
            QMessageBox.critical(self, "Error", "OpenRAM path is not set or invalid.")
            return
        
        tech_base_path = os.path.join(openram_path_field.text(), TECHNOLOGY_PATH)
        os.makedirs(tech_base_path, exist_ok=True)
        target_path = os.path.join(tech_base_path, folder_name)

        if os.path.exists(target_path):
            reply = QMessageBox.question(self, "Folder Exists", 
                                           f"The technology '{folder_name}' already exists. Overwrite?",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
            try:
                shutil.rmtree(target_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove existing folder: {e}")
                return

        try:
            shutil.copytree(folder_path, target_path)
            
            with open(TECHNOLOGY_FILE, "a+") as f:
                f.seek(0)
                techs = [line.strip() for line in f]
                if folder_name not in techs:
                    f.write(f"\n{folder_name}")

            QMessageBox.information(self, "Success", f"Folder uploaded to:\n{target_path}")

            self.populate_tech_list(list_widget)
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item.text() == folder_name:
                    item.setSelected(True)
                    list_widget.scrollToItem(item)
                    break
            # self.set_modified()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to upload folder:\n{e}")