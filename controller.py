import os
import shutil
import subprocess
import glob
import tempfile
from PySide6.QtWidgets import QMessageBox, QTextEdit, QInputDialog, QFileDialog, QVBoxLayout, QLabel, QListWidget,     QPushButton, QWidget, QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem, QDialog, QHeaderView
from PySide6.QtCore import QCoreApplication, QProcess, QObject, Signal, QThread

from config_loader import _load_config_file
from config_editor import ConfigEditor
from advanced_config_editor import AdvancedConfigEditor
from constants import MANDATORY_CONFIG_KEYS, ADVANCED_CONFIG_FILE, HOME_SCREEN_MESSAGE, USERS_CONFIG_DIR, OUTPUT_PATH
from dialogs import LoadConfigDialog, SaveConfigDialog

from pathlib import Path
import time


class Controller:
    def __init__(self, ui):
        self.ui = ui
        self.config = {}
        self.config_path = None
        self.process = None
        self.temp_script_path = None
        self.download_process = None

    def _get_remote_user_host(self):
        advanced_config = _load_config_file(ADVANCED_CONFIG_FILE)
        openram_path = advanced_config.get("openram_path", "")
        if '@' in openram_path and ':' in openram_path:
            try:
                user_host, remote_path = openram_path.split(':', 1)
                user, host = user_host.split('@', 1)
                return user, host, remote_path
            except ValueError:
                QMessageBox.critical(self.ui, "Error", "Invalid remote path format in advanced settings. Use user@host:/path/to/openram")
                return None, None, None
        return None, None, None

    def _create_temp_script(self, command_to_run):
        """Creates a temporary shell script to run a command in the OpenRAM environment."""
        advanced_config = _load_config_file(ADVANCED_CONFIG_FILE)
        openram_path = advanced_config.get("openram_path")

        if not openram_path:
            QMessageBox.critical(self.ui, "Error", "OpenRAM path not set in advanced settings.")
            return None

        openram_activate_script = os.path.join(openram_path, "openram_env", "bin", "activate")
        miniconda_activate_script = os.path.join(openram_path, "miniconda", "bin", "activate")
        setpaths_script = os.path.join(openram_path, "setpaths.sh")

        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh', encoding='utf-8') as f:
                f.write("#!/bin/bash\n")
                f.write(f"source {openram_activate_script}\n")
                f.write(f"source {miniconda_activate_script}\n")
                f.write(f"source {setpaths_script}\n")
                f.write(f"{command_to_run}\n")
                temp_script_path = f.name

            os.chmod(temp_script_path, 0o755)
            return temp_script_path
        except Exception as e:
            QMessageBox.critical(self.ui, "Error", f"Failed to create temporary script: {e}")
            return None

    def load_config(self):
        user, host, remote_path = self._get_remote_user_host()
        dialog = LoadConfigDialog()
        display_name = None

        if user and host:
            remote_users_config_dir = os.path.join(remote_path, USERS_CONFIG_DIR)
            # Ensure the remote directory exists
            mkdir_command = ["ssh", "-i", os.path.join(os.path.dirname(__file__), "openram_key"), f"{user}@{host}", f"mkdir -p {remote_users_config_dir}"]
            try:
                subprocess.run(mkdir_command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                QMessageBox.critical(self.ui, "SSH Error", f"Failed to create remote directory: {e.stderr}")
                return

            # List files in the remote directory
            ls_command = ["ssh", "-i", os.path.join(os.path.dirname(__file__), "openram_key"), f"{user}@{host}", f"ls {remote_users_config_dir}"]
            try:
                process = subprocess.run(ls_command, check=True, capture_output=True, text=True)
                config_files = [f for f in process.stdout.strip().split('\n') if f.endswith(".py")]
                dialog.list_widget.addItems([os.path.splitext(f)[0] for f in config_files])
            except subprocess.CalledProcessError as e:
                QMessageBox.critical(self.ui, "SSH Error", f"Failed to list remote config files: {e.stderr}")
                return
        else:
            config_files = [f for f in os.listdir(USERS_CONFIG_DIR) if f.endswith(".py")]
            dialog.list_widget.addItems([os.path.splitext(f)[0] for f in config_files])

        if dialog.exec():
            selected_config = dialog.get_selected_config()
            if user and host:
                display_name = selected_config
                remote_users_config_dir = os.path.join(remote_path, USERS_CONFIG_DIR)
                remote_config_path = os.path.join(remote_users_config_dir, f"{selected_config}.py")
                
                try:
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as tmp:
                        scp_command = ["scp", "-i", os.path.join(os.path.dirname(__file__), "openram_key"), f"{user}@{host}:{remote_config_path}", tmp.name]
                        subprocess.run(scp_command, check=True)
                        self.config_path = tmp.name
                except subprocess.CalledProcessError as e:
                    QMessageBox.critical(self.ui, "SFTP Error", f"Failed to download config file: {e.stderr}")
                    return
            else:
                self.config_path = os.path.join(USERS_CONFIG_DIR, f"{selected_config}.py")

            if self.ui.editor:
                self.ui.scroll_area.takeWidget()
                self.ui.editor.deleteLater()
                self.ui.editor = None
            self.ui.editor = ConfigEditor(self.config_path, display_name=display_name)
            self.ui.editor.setMinimumWidth(400)
            self.ui.scroll_area.setWidget(self.ui.editor)

    def create_new_config(self):
        self.ui.editor = ConfigEditor(None)
        self.ui.editor.setMinimumWidth(400)
        self.ui.scroll_area.setWidget(self.ui.editor)

    def save_config(self):
        if not self.ui.editor:
            QMessageBox.warning(None, "No Config", "Nothing to save.")
            return

        current_config = self.ui.editor.get_config()
        missing_fields = [field for field in MANDATORY_CONFIG_KEYS if not current_config.get(field)]

        if missing_fields:
            reply = QMessageBox.warning(
                None,
                "Missing Mandatory Fields",
                f"The following mandatory fields are empty: {', '.join(missing_fields)}.\n\nDo you want to save anyway?",
                QMessageBox.Save | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                return

        dialog = SaveConfigDialog()
        if dialog.exec():
            config_name = dialog.get_config_name()
            if config_name:
                user, host, remote_path = self._get_remote_user_host()
                if user and host:
                    remote_users_config_dir = os.path.join(remote_path, USERS_CONFIG_DIR)
                    remote_config_path = os.path.join(remote_users_config_dir, f"{config_name}.py")
                    
                    try:
                        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as tmp:
                            self.ui.editor.save_config(tmp.name)
                            scp_command = ["scp", "-i", os.path.join(os.path.dirname(__file__), "openram_key"), tmp.name, f"{user}@{host}:{remote_config_path}"]
                            subprocess.run(scp_command, check=True)
                        QMessageBox.information(self.ui, "Save Complete", f"Configuration saved as {config_name} on the OpenRAM Server.")
                    except subprocess.CalledProcessError as e:
                        QMessageBox.critical(self.ui, "SFTP Error", f"Failed to upload config file: {e.stderr}")
                else:
                    path = os.path.join(USERS_CONFIG_DIR, f"{config_name}.py")
                    self.ui.editor.save_config(path)

    def run_openram(self):
        if self.process and self.process.state() != QProcess.NotRunning:
            QMessageBox.warning(self.ui, "Warning", "An OpenRAM process is already running.")
            return

        if not self.config_path:
            QMessageBox.warning(self.ui, "Warning", "Please load a config file first.")
            return

        current_config = _load_config_file(self.config_path)
        missing_fields = [field for field in MANDATORY_CONFIG_KEYS if not current_config.get(field)]
        if missing_fields:
            QMessageBox.critical(self.ui, "Error", f"Missing mandatory fields: {', '.join(missing_fields)}")
            return

        self.ui.run_button.setEnabled(False)
        self.ui.run_button.setText("Running...")
        self.ui.log_output.clear()
        self.ui.log_output.append("Running OpenRAM... please wait, this may take a while.")
        QCoreApplication.processEvents()

        advanced_config = _load_config_file(ADVANCED_CONFIG_FILE)
        openram_path = advanced_config.get("openram_path", "")

        is_remote = '@' in openram_path and ':' in openram_path

        if is_remote:
            self.ui.log_output.append("Remote OpenRAM path detected.")
            
            user, host, remote_path = self._get_remote_user_host()
            if not user:
                self.ui.run_button.setEnabled(True)
                self.ui.run_button.setText("Run OpenRAM")
                return

            remote_users_config_dir = os.path.join(remote_path, USERS_CONFIG_DIR)
            remote_config_filename = os.path.basename(self.config_path)
            remote_config_path = os.path.join(remote_users_config_dir, remote_config_filename)

            user_host, remote_openram_path = openram_path.split(':', 1)
            sram_compiler_script = os.path.join(remote_openram_path, "sram_compiler.py")
            remote_openram_activate_script = os.path.join(remote_openram_path, "openram_env", "bin", "activate")
            remote_miniconda_activate_script = os.path.join(remote_openram_path, "miniconda", "bin", "activate")
            remote_setpaths_script = os.path.join(remote_openram_path, "setpaths.sh")

            remote_command = f"""
                cd {remote_openram_path} && \
                source {remote_openram_activate_script} && \
                source {remote_miniconda_activate_script} && \
                source {remote_setpaths_script} && \
                python3 -u {sram_compiler_script} {remote_config_path}                 
            """

            ssh_command = [
                "ssh",
                "-i", os.path.join(os.path.dirname(__file__), "openram_key"),
                f"{user}@{host}",
                remote_command
            ]

            self.process = QProcess()
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.on_output_ready)
            self.process.finished.connect(lambda code, status: self.on_run_finished(code, status))
            self.process.start("ssh", ssh_command[1:])

        else:  # Local execution
            sram_compiler_script = os.path.join(openram_path, "sram_compiler.py")
            command_to_run = f"python3 -u {sram_compiler_script} {self.config_path}"

            self.temp_script_path = self._create_temp_script(command_to_run)
            if not self.temp_script_path:
                self.ui.run_button.setEnabled(True)
                self.ui.run_button.setText("Run OpenRAM")
                return

            self.process = QProcess()
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.on_output_ready)
            self.process.finished.connect(lambda code, status: self.on_run_finished(code, status))
            self.process.start("bash", [self.temp_script_path])

    def _append_log(self, message):
        self.ui.log_output.append(message)

    def on_output_ready(self):
        output = self.process.readAllStandardOutput().data().decode(errors='replace')
        self.ui.log_output.append(output.strip())

    def on_run_finished(self, exitCode, exitStatus=QProcess.NormalExit):
        self.ui.log_output.append(f"\nOpenRAM process finished.")
        self.ui.log_output.append(f"Exit Code: {exitCode}")
        
        if isinstance(exitStatus, QProcess.ExitStatus):
             self.ui.log_output.append(f"Exit Status: {'Normal' if exitStatus == QProcess.NormalExit else 'Crash'}")

        self.ui.run_button.setEnabled(True)
        self.ui.run_button.setText("Run OpenRAM")

        if self.temp_script_path and os.path.exists(self.temp_script_path):
            os.unlink(self.temp_script_path)
            self.temp_script_path = None

        self.process = None

    def view_gds(self):
        if not self.config_path:
            QMessageBox.warning(self.ui, "Warning", "Please load a config file first.")
            return

        config = _load_config_file(self.config_path)
        output_path_from_config = config.get(OUTPUT_PATH, ".")

        advanced_config = _load_config_file(ADVANCED_CONFIG_FILE)
        openram_path = advanced_config.get("openram_path", "")
        is_remote = '@' in openram_path and ':' in openram_path

        gds_file_to_open = None

        if is_remote:
            self.ui.log_output.append("Remote GDS: Downloading file...")
            QCoreApplication.processEvents()

            try:
                user_host, remote_openram_path = openram_path.split(':', 1)
                user, host = user_host.split('@', 1)
            except ValueError:
                QMessageBox.critical(self.ui, "Error", "Invalid remote path format. Use user@host:/path/to/openram")
                return

            remote_output_path = os.path.join(remote_openram_path, output_path_from_config)
            list_gds_command = f'ls -1 {remote_output_path}/*.gds 2>/dev/null'
            
            try:
                ssh_command = ["ssh", "-i", os.path.join(os.path.dirname(__file__), "openram_key"), f"{user}@{host}", list_gds_command]
                process = subprocess.run(ssh_command, check=True, capture_output=True, text=True)
                gds_files_full_paths = process.stdout.strip().split('\n')
                gds_files_full_paths = [f for f in gds_files_full_paths if f]
                err = process.stderr.strip()
                if err:
                    QMessageBox.warning(self.ui, "Warning", f"Could not list remote GDS files: {err}")
                    return
            except subprocess.CalledProcessError as e:
                QMessageBox.warning(self.ui, "Warning", f"Error listing remote GDS files: {e.stderr}")
                return

            if not gds_files_full_paths:
                QMessageBox.warning(self.ui, "Warning", f"No GDS file found in remote directory: {remote_output_path}")
                return

            remote_gds_file_path = None
            if len(gds_files_full_paths) == 1:
                remote_gds_file_path = gds_files_full_paths[0]
            else:
                file_names = [os.path.basename(f) for f in gds_files_full_paths]
                file_name, ok = QInputDialog.getItem(self.ui, "Select Remote GDS File", "Multiple GDS files found...", file_names, 0, False)
                if ok and file_name:
                    remote_gds_file_path = next((path for path in gds_files_full_paths if os.path.basename(path) == file_name), None)

            if remote_gds_file_path:
                try:
                    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.gds') as tmp:
                        self.ui.log_output.append(f"Downloading {os.path.basename(remote_gds_file_path)} to temporary file...")
                        QCoreApplication.processEvents()
                        scp_command = ["scp", "-i", os.path.join(os.path.dirname(__file__), "openram_key"), f"{user}@{host}:{remote_gds_file_path}", tmp.name]
                        subprocess.run(scp_command, check=True)
                        gds_file_to_open = tmp.name
                    self.ui.log_output.append("Download complete.")
                except subprocess.CalledProcessError as e:
                    QMessageBox.critical(self.ui, "SFTP Error", f"Failed to download GDS file: {e.stderr}")
                    return
        
        else:  # Local execution
            gds_files = glob.glob(os.path.join(output_path_from_config, "*.gds"))

            if not gds_files:
                QMessageBox.warning(self.ui, "Warning", f"No GDS file found in {output_path_from_config}")
                return

            if len(gds_files) == 1:
                gds_file_to_open = gds_files[0]
            else:
                file_names = [os.path.basename(f) for f in gds_files]
                file_name, ok = QInputDialog.getItem(self.ui, "Select GDS File", "Multiple GDS files found...",
                                                     file_names, 0, False)
                if ok and file_name:
                    gds_file_to_open = os.path.join(output_path_from_config, file_name)

        if gds_file_to_open:
            self.ui.log_output.append(f"Opening {gds_file_to_open} with KLayout...")
            command = f"klayout {gds_file_to_open}"
            QProcess.startDetached("bash", ["-c", command])

    def view_output(self):
        if not self.config_path:
            QMessageBox.warning(self.ui, "Warning", "Please load a config file first.")
            return

        config = _load_config_file(self.config_path)
        output_path_from_config = config.get(OUTPUT_PATH, ".")
        config_name = os.path.splitext(os.path.basename(self.config_path))[0]

        output_widget = QWidget()
        layout = QVBoxLayout(output_widget)

        config_label = QLabel(f"Current Config:   <b>{config_name}</b>")
        layout.addWidget(config_label)

        file_list_label = QLabel("Output Files:")
        layout.addWidget(file_list_label)

        file_list = QListWidget()
        layout.addWidget(file_list)

        advanced_config = _load_config_file(ADVANCED_CONFIG_FILE)
        openram_path = advanced_config.get("openram_path", "")
        is_remote = '@' in openram_path and ':' in openram_path

        source_path_for_download = ""
        
        if is_remote:
            try:
                user_host, remote_openram_path = openram_path.split(':', 1)
                user, host = user_host.split('@', 1)
                remote_output_path = os.path.join(remote_openram_path, output_path_from_config)
                source_path_for_download = remote_output_path
            except ValueError:
                file_list.addItem("Invalid remote path format in advanced settings.")
                QMessageBox.critical(self.ui, "Error", "Invalid remote path format. Use user@host:/path/to/openram")
                return

            list_files_command = f'ls -F {remote_output_path} 2>/dev/null'
            try:
                ssh_command = ["ssh", "-i", os.path.join(os.path.dirname(__file__), "openram_key"), f"{user}@{host}", list_files_command]
                process = subprocess.run(ssh_command, check=True, capture_output=True, text=True)
                files = process.stdout.strip().split('\n')
                err = process.stderr.strip()
                if err:
                     file_list.addItem(f"Could not list remote directory (or it's empty).")
                     file_list.addItem(f"Error: {err}")
                else:
                    file_list.addItems([f for f in files if f])
            except subprocess.CalledProcessError as e:
                file_list.addItem(f"Error listing remote files: {e.stderr}")

        else:  # Local execution
            source_path_for_download = output_path_from_config
            try:
                files = sorted(os.listdir(output_path_from_config))
                file_list.addItems(files)
            except FileNotFoundError:
                file_list.addItem("Output directory not found.")

        button_layout = QHBoxLayout()
        self.ui.download_button = QPushButton("Download Output Folder")
        self.ui.download_button.clicked.connect(lambda: self.download_output_folder(source_path_for_download, is_remote))
        button_layout.addWidget(self.ui.download_button)

        view_gds_button = QPushButton("View GDS")
        view_gds_button.clicked.connect(self.view_gds)
        button_layout.addWidget(view_gds_button)
        
        layout.addLayout(button_layout)

        if self.ui.editor:
            self.ui.scroll_area.takeWidget()
            self.ui.editor.deleteLater()
            self.ui.editor = None

        self.ui.scroll_area.setWidget(output_widget)

    def download_output_folder(self, source_path, is_remote):
        if self.download_process and self.download_process.state() != QProcess.NotRunning:
            QMessageBox.warning(self.ui, "Warning", "A download is already in progress.")
            return

        suggested_name = os.path.basename(source_path.strip('/')) + ".zip"
        
        home_dir = str(Path.home())
        initial_dir = os.path.join(home_dir, "Downloads")
        if not os.path.isdir(initial_dir):
            initial_dir = home_dir
        
        save_path, _ = QFileDialog.getSaveFileName(self.ui, "Save Zip File", os.path.join(initial_dir, suggested_name), "Zip Files (*.zip)")

        if not save_path:
            self.ui.log_output.append("Download cancelled by user.")
            return

        self.ui.download_button.setEnabled(False)
        self.ui.download_button.setText("Zipping...")
        self.ui.log_output.append("\n--- Starting Download ---")

        if is_remote:
            self.ui.log_output.append(f"Zipping remote folder: {source_path}")
            
            advanced_config = _load_config_file(ADVANCED_CONFIG_FILE)
            openram_path = advanced_config.get("openram_path", "")
            try:
                user_host, _ = openram_path.split(':', 1)
                user, host = user_host.split('@', 1)

                remote_zip_path = f"/tmp/{os.path.basename(source_path)}.zip"
                
                # Command to zip the folder on the remote server
                zip_command = f"cd {os.path.dirname(source_path)} && zip -r {remote_zip_path} {os.path.basename(source_path)}"
                
                ssh_zip_command = ["ssh", "-i", os.path.join(os.path.dirname(__file__), "openram_key"), f"{user}@{host}", zip_command]

                # Run zipping process
                process = subprocess.run(ssh_zip_command, capture_output=True, text=True)
                if process.returncode != 0:
                    QMessageBox.critical(self, "Error", f"Failed to zip remote folder: {process.stderr}")
                    self.ui.download_button.setEnabled(True)
                    self.ui.download_button.setText("Download Output Folder")
                    return

                self.ui.log_output.append("Zipping complete. Starting download...")
                self.ui.download_button.setText("Downloading...")

                # Command to download the zip file
                scp_command = ["scp", "-i", os.path.join(os.path.dirname(__file__), "openram_key"), f"{user}@{host}:{remote_zip_path}", save_path]

                self.download_process = QProcess()
                self.download_process.setProcessChannelMode(QProcess.MergedChannels)
                self.download_process.readyReadStandardOutput.connect(self._on_download_output_ready)
                self.download_process.finished.connect(lambda code, status: self.on_download_process_finished(code, status, remote_zip_path=remote_zip_path))
                self.download_process.start("scp", scp_command[1:])

            except Exception as e:
                QMessageBox.critical(self.ui, "Error", f"An unexpected error occurred: {e}")
                self.ui.download_button.setEnabled(True)
                self.ui.download_button.setText("Download Output Folder")

        else: # Local zipping
            try:
                self.ui.log_output.append(f"Zipping local folder {source_path} to {save_path}...")
                shutil.make_archive(os.path.splitext(save_path)[0], 'zip', source_path)
                QMessageBox.information(self.ui, "Success", f"Output folder zipped successfully to {save_path}")
            except Exception as e:
                QMessageBox.critical(self.ui, "Error", f"An unexpected error occurred during local zipping: {e}")
            finally:
                self.ui.download_button.setEnabled(True)
                self.ui.download_button.setText("Download Output Folder")

    def _on_download_output_ready(self):
        output = self.download_process.readAllStandardOutput().data().decode(errors='replace')
        self._append_log(output.strip())

    def on_download_process_finished(self, exitCode, exitStatus, remote_zip_path=None):
        self.ui.download_button.setEnabled(True)
        self.ui.download_button.setText("Download Output Folder")
        
        output = self.download_process.readAllStandardOutput().data().decode(errors='replace')
        if output:
            self.ui.log_output.append(output.strip())

        if exitCode == 0:
            QMessageBox.information(self.ui, "Success", f"Output folder downloaded successfully.")
            if remote_zip_path:
                # Clean up the remote zip file
                try:
                    advanced_config = _load_config_file(ADVANCED_CONFIG_FILE)
                    openram_path = advanced_config.get("openram_path", "")
                    user_host, _ = openram_path.split(':', 1)
                    user, host = user_host.split('@', 1)
                    
                    rm_command = f"rm {remote_zip_path}"
                    ssh_rm_command = ["ssh", "-i", os.path.join(os.path.dirname(__file__), "openram_key"), f"{user}@{host}", rm_command]
                    subprocess.run(ssh_rm_command)
                    self.ui.log_output.append(f"Cleaned up remote file: {remote_zip_path}")
                except Exception as e:
                    self.ui.log_output.append(f"Warning: Failed to clean up remote zip file: {e}")
        else:
            QMessageBox.critical(self.ui, "Error", f"Download process failed with exit code {exitCode}.")
        
        self.ui.log_output.append(f"\n--- Download Finished ---")
        self.download_process = None

    def show_advanced_settings(self):
        if self.ui.editor:
            self.ui.scroll_area.takeWidget()
            self.ui.editor.deleteLater()
            self.ui.editor = None

        self.ui.editor = AdvancedConfigEditor()
        self.ui.editor.setMinimumWidth(400)
        self.ui.scroll_area.setWidget(self.ui.editor)

    def _view_config_popup(self, file_path):
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            dialog = QDialog(self.ui)
            dialog.setWindowTitle(os.path.basename(file_path))
            layout = QVBoxLayout(dialog)
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setText(content)
            layout.addWidget(text_edit)
            
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self.ui, "Error", f"Failed to read config file: {e}")

    def show_home_screen(self):
        if self.ui.editor:
            self.ui.scroll_area.takeWidget()
            self.ui.editor.deleteLater()
            self.ui.editor = None

        home_widget = QWidget()
        layout = QVBoxLayout(home_widget)

        # Recent Activity Table
        activity_label = QLabel("<b>Recent Activity</b>")
        layout.addWidget(activity_label)
        
        table = self._get_file_properties_as_table(USERS_CONFIG_DIR)
        layout.addWidget(table)

        # # Advanced Settings
        # advanced_config_content = ""
        # try:
        #     advanced_config = _load_config_file(ADVANCED_CONFIG_FILE)
        #     advanced_config_content = "<br><br><b>--- Current Advanced Settings ---</b><br>"
        #     for key, value in advanced_config.items():
        #         advanced_config_content += f"{key} = {value}<br>"
        # except FileNotFoundError:
        #     advanced_config_content = "\n\nAdvanced config file not found."
        # except Exception as e:
        #     advanced_config_content = f"\n\nError loading advanced config: {e}"

        # advanced_settings_label = QLabel(advanced_config_content)
        # layout.addWidget(advanced_settings_label)

        self.ui.scroll_area.setWidget(home_widget)

    def _get_file_properties_as_table(self, folder_path: str):
        path = Path(folder_path)

        if not path.exists() or not path.is_dir():
            label = QLabel(f"Path '{folder_path}' does not exist or is not a directory.")
            return label

        # Gather all files with access time
        files = []
        for file in path.iterdir():
            if file.is_file() and file.suffix == '.py':
                stats = file.stat()
                files.append({
                    "name": file.stem,
                    "path": str(file),
                    "accessed": stats.st_atime,
                    "modified": stats.st_mtime
                })

        # Sort by access time, descending, and take the last 3 accessed files
        recent_files = sorted(files, key=lambda x: x["accessed"], reverse=True)[:3]

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Config Name", "Last Accessed", "Last Modified", "Actions"])
        table.setRowCount(len(recent_files))

        for i, file in enumerate(recent_files):
            table.setItem(i, 0, QTableWidgetItem(file['name']))
            table.setItem(i, 1, QTableWidgetItem(time.strftime('%d %b, %Y %H:%M:%S', time.localtime(file["accessed"]))))
            table.setItem(i, 2, QTableWidgetItem(time.strftime('%d %b, %Y %H:%M:%S', time.localtime(file["modified"]))))
            
            view_button = QPushButton("View Config")
            view_button.clicked.connect(lambda _, p=file["path"]: self._view_config_popup(p))
            table.setCellWidget(i, 3, view_button)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)        

        return table

    def show_about(self):
        about_text = """
        <h2>OpenRAM UI</h2>
        <p>This is a graphical user interface for the OpenRAM memory compiler.</p>
        <p>Version: 0.1</p>
        <p>For more information, please visit the 
        <a href='https://openram.org/'>OpenRAM website</a>.</p>
        """
        QMessageBox.about(self.ui, "About OpenRAM UI", about_text)
