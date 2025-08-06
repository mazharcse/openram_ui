# advanced_config_editor.py
from PySide6.QtWidgets import (QWidget, QFormLayout, QLineEdit, QPushButton, QVBoxLayout, 
                             QFileDialog, QHBoxLayout, QMessageBox, QListWidget, QInputDialog)
from PySide6.QtCore import Qt, QDir
import ast
import os
from config_loader import _load_config_file
from constants import ADVANCED_CONFIG_FILE, TECHNOLOGY_PATH, OPENRAM_PATH, TECHNOLOGY_FILE
import shutil
import subprocess
import paramiko


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
                field.textChanged.connect(self.refresh_tech_list)
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
            
            elif key in ["ssh_host", "ssh_user", "ssh_password"]:
                # We will handle these separately
                continue

            else:
                field = QLineEdit(str(value))
                self.fields[key] = field
                self.form.addRow(key, field)
                field.textChanged.connect(self.set_modified)
        
        self.test_ssh_button = QPushButton("Test SSH Connection")
        self.test_ssh_button.clicked.connect(self.test_ssh_connection)
        
        self.layout.addWidget(self.test_ssh_button)


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

    def test_ssh_connection(self):
        openram_path = self.fields[OPENRAM_PATH].text()

        if not openram_path:
            QMessageBox.warning(self, "Missing Information", "Please fill in OpenRAM Path.")
            return
        
        try:
            user_host, remote_path = openram_path.split(':', 1)
            user, host = user_host.split('@', 1)
        except ValueError:
            QMessageBox.critical(self, "Error", "Invalid remote path format. Use user@host:/path/to/openram")
            return

        password, ok = QInputDialog.getText(self, "SSH Password", f"Enter password for {user}@{host}:", QLineEdit.Password)

        if not ok:
            return # User cancelled

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, username=user, password=password, timeout=5)
            client.close()
            QMessageBox.information(self, "Success", "SSH connection successful!")
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", f"Failed to connect: {e}")

    def populate_tech_list(self, list_widget: QListWidget):
        list_widget.clear()

        openram_path_field = self.fields.get(OPENRAM_PATH)
        openram_path = openram_path_field.text() if openram_path_field else ""
        is_remote = '@' in openram_path and ':' in openram_path

        techs = []
        if is_remote:
            try:
                user_host, remote_openram_path = openram_path.split(':', 1)
                user, host = user_host.split('@', 1)
                remote_tech_file = os.path.join(remote_openram_path, os.path.basename(TECHNOLOGY_FILE))

                # Prompt for password
                password, ok = QInputDialog.getText(self, "SSH Password", f"Enter password for {user}@{host}:", QLineEdit.Password)
                if not ok:
                    return # User cancelled

                # Use Paramiko to fetch the file content
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(host, username=user, password=password, timeout=5)
                
                stdin, stdout, stderr = client.exec_command(f'cat {remote_tech_file}')
                
                exit_status = stdout.channel.recv_exit_status()
                if exit_status == 0:
                    techs = [line.strip() for line in stdout.read().decode().strip().split('\n') if line.strip()]
                else:
                    error_message = stderr.read().decode().strip()
                    if not error_message:
                        error_message = f"File not found or permission issue on remote server. Exit code: {exit_status}"
                    QMessageBox.warning(self, "Warning", f"Could not read remote technology file.\nError: {error_message}")

                client.close()

            except Exception as e:
                QMessageBox.warning(self, "Warning", f"An error occurred while fetching remote technologies: {e}")
        else:
            try:
                with open(TECHNOLOGY_FILE, "r") as f:
                    techs = [line.strip() for line in f if line.strip()]
            except FileNotFoundError:
                # This is not an error, the file might not be created yet.
                pass
        
        if techs:
            list_widget.addItems(techs)

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

    def refresh_tech_list(self):
        tech_list_widget = self.fields.get("tech_name")
        if isinstance(tech_list_widget, QListWidget):
            self.populate_tech_list(tech_list_widget)

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
        if not openram_path_field or not openram_path_field.text():
            QMessageBox.critical(self, "Error", "OpenRAM path is not set.")
            return
        
        openram_path = openram_path_field.text()
        is_remote = '@' in openram_path and ':' in openram_path

        if is_remote:
            try:
                user_host, remote_openram_path = openram_path.split(':', 1)
                user, host = user_host.split('@', 1)
            except ValueError:
                QMessageBox.critical(self, "Error", "Invalid remote path format. Use user@host:/path/to/openram")
                return

            password, ok = QInputDialog.getText(self, "SSH Password", f"Enter password for {user}@{host}:", QLineEdit.Password)
            if not ok:
                return # User cancelled

            remote_tech_base_path = os.path.join(remote_openram_path, TECHNOLOGY_PATH)
            remote_target_path = os.path.join(remote_tech_base_path, folder_name)

            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(host, username=user, password=password, timeout=5)
                sftp = client.open_sftp()

                # 1. Check if the folder exists and ask to overwrite
                try:
                    sftp.stat(remote_target_path)
                    # If stat succeeds, directory exists
                    reply = QMessageBox.question(self, "Folder Exists",
                                                   f"The remote technology '{folder_name}' already exists. Overwrite?",
                                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.No:
                        client.close()
                        return
                    # If yes, remove the remote directory first
                    stdin, stdout, stderr = client.exec_command(f'rm -rf {remote_target_path}')
                    exit_status = stdout.channel.recv_exit_status()
                    if exit_status != 0:
                        raise Exception(f"Failed to remove remote directory: {stderr.read().decode()}")
                except FileNotFoundError:
                    # This is good, the directory doesn't exist
                    pass

                # 2. Create the base directory and upload the folder recursively
                try:
                    sftp.stat(remote_tech_base_path)
                except FileNotFoundError:
                    sftp.mkdir(remote_tech_base_path)
                
                QMessageBox.information(self, "Uploading", f"Uploading folder to {user_host}:{remote_target_path}")
                
                # Create top-level directory for the PDK
                sftp.mkdir(remote_target_path)

                for dirpath, _, filenames in os.walk(folder_path):
                    remote_dirpath = os.path.join(remote_target_path, os.path.relpath(dirpath, folder_path)).replace("\\", "/")
                    for filename in filenames:
                        local_file_path = os.path.join(dirpath, filename)
                        remote_file_path = os.path.join(remote_dirpath, filename).replace("\\", "/")
                        # Ensure remote subdirectory exists
                        try:
                            sftp.stat(remote_dirpath)
                        except FileNotFoundError:
                            sftp.mkdir(remote_dirpath)
                        sftp.put(local_file_path, remote_file_path)

                # 3. Update the remote technology.txt
                remote_tech_file = os.path.join(remote_openram_path, os.path.basename(TECHNOLOGY_FILE))
                append_command = f"grep -qxF '{folder_name}' {remote_tech_file} || echo '{folder_name}' >> {remote_tech_file}"
                stdin, stdout, stderr = client.exec_command(append_command)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                     raise Exception(f"Failed to update remote technology.txt: {stderr.read().decode()}")

                client.close()
                QMessageBox.information(self, "Success", f"Folder uploaded to:\n{user_host}:{remote_target_path}")
                self.populate_tech_list(list_widget)
                self.set_modified()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred during the remote operation:\n{e}")
                if 'client' in locals() and client.get_transport() and client.get_transport().is_active():
                    client.close()
                return

        else: # Local upload logic
            if not os.path.isdir(openram_path):
                QMessageBox.critical(self, "Error", "Local OpenRAM path is not a valid directory.")
                return

            tech_base_path = os.path.join(openram_path, TECHNOLOGY_PATH)
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
                self.set_modified()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to upload folder:\n{e}")