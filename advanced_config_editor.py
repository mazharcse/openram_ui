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

        ssh_key_path = os.path.join(os.path.dirname(__file__), "openram_key")
        if not os.path.exists(ssh_key_path):
            QMessageBox.critical(self, "Error", f"SSH key file not found: {ssh_key_path}")
            return

        try:
            key = paramiko.RSAKey.from_private_key_file(ssh_key_path)
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, username=user, pkey=key, timeout=5)
            client.close()
            QMessageBox.information(self, "Success", "SSH connection successful!")
        except paramiko.AuthenticationException:
            QMessageBox.critical(self, "Connection Failed", "Authentication failed. Check your SSH key and permissions.")
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

                ssh_key_path = os.path.join(os.path.dirname(__file__), "openram_key")
                if not os.path.exists(ssh_key_path):
                    QMessageBox.critical(self, "Error", f"SSH key file not found: {ssh_key_path}")
                    return

                key = paramiko.RSAKey.from_private_key_file(ssh_key_path)
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(host, username=user, pkey=key, timeout=5)
                
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
            
    def _sftp_mkdir_recursive(self, sftp, remote_path):
        """Creates a remote directory recursively."""
        current_path = ""
        # Handle absolute paths by preserving the leading slash
        if remote_path.startswith('/'):
            current_path = '/'
        
        for part in remote_path.strip('/').split('/'):
            if not part:
                continue
            current_path = os.path.join(current_path, part).replace("\\", "/")
            try:
                sftp.stat(current_path)
            except FileNotFoundError:
                sftp.mkdir(current_path)

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
            client = None  # Initialize client to None
            try:
                user_host, remote_openram_path_raw = openram_path.split(':', 1)
                user, host = user_host.split('@', 1)

                ssh_key_path = os.path.join(os.path.dirname(__file__), "openram_key")
                if not os.path.exists(ssh_key_path):
                    QMessageBox.critical(self, "Error", f"SSH key file not found: {ssh_key_path}")
                    return

                key = paramiko.RSAKey.from_private_key_file(ssh_key_path)
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(host, username=user, pkey=key, timeout=5)
                sftp = client.open_sftp()

                # Resolve remote home directory
                stdin, stdout, stderr = client.exec_command("echo $HOME")
                remote_home = stdout.read().decode().strip()
                
                if remote_openram_path_raw.startswith('~/'):
                    remote_openram_path = os.path.join(remote_home, remote_openram_path_raw[2:]).replace("\\", "/")
                else:
                    remote_openram_path = remote_openram_path_raw.replace("\\", "/")

                remote_tech_base_path = os.path.join(remote_openram_path, TECHNOLOGY_PATH).replace("\\", "/")
                remote_target_path = os.path.join(remote_tech_base_path, folder_name).replace("\\", "/")

                # 1. Check if the folder exists and ask to overwrite
                try:
                    sftp.stat(remote_target_path)
                    reply = QMessageBox.question(self, "Folder Exists",
                                                   f"The remote technology '{folder_name}' already exists. Overwrite?",
                                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.No:
                        return
                    stdin, stdout, stderr = client.exec_command(f'rm -rf "{remote_target_path}"')
                    exit_status = stdout.channel.recv_exit_status()
                    if exit_status != 0:
                        raise Exception(f"Failed to remove remote directory: {stderr.read().decode()}")
                except FileNotFoundError:
                    pass # Good, it doesn't exist

                # 2. Recursively create directory structure and upload
                QMessageBox.information(self, "Uploading", f"Uploading folder to {user_host}:{remote_target_path}")
                
                self._sftp_mkdir_recursive(sftp, remote_target_path)

                for dirpath, _, filenames in os.walk(folder_path):
                    rel_dir = os.path.relpath(dirpath, folder_path)
                    if rel_dir == '.':
                        remote_dir = remote_target_path
                    else:
                        remote_dir = os.path.join(remote_target_path, rel_dir).replace("\\", "/")
                    
                    self._sftp_mkdir_recursive(sftp, remote_dir)

                    for filename in filenames:
                        local_file = os.path.join(dirpath, filename)
                        remote_file = os.path.join(remote_dir, filename).replace("\\", "/")
                        sftp.put(local_file, remote_file)

                # 3. Update the remote technology.txt
                remote_tech_file = os.path.join(remote_openram_path, os.path.basename(TECHNOLOGY_FILE))
                append_command = f"grep -qxF '{folder_name}' '{remote_tech_file}' || echo '{folder_name}' >> '{remote_tech_file}'"
                stdin, stdout, stderr = client.exec_command(append_command)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                     if "No such file" in stderr.read().decode():
                         stdin, stdout, stderr = client.exec_command(f"echo '{folder_name}' > '{remote_tech_file}'")
                         exit_status = stdout.channel.recv_exit_status()
                         if exit_status != 0:
                             raise Exception(f"Failed to create remote technology.txt: {stderr.read().decode()}")
                     else:
                        raise Exception(f"Failed to update remote technology.txt: {stderr.read().decode()}")

                QMessageBox.information(self, "Success", f"Folder uploaded to:\n{user_host}:{remote_target_path}")
                self.populate_tech_list(list_widget)
                self.set_modified()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred during the remote operation:\n{e}")
            finally:
                if client and client.get_transport() and client.get_transport().is_active():
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