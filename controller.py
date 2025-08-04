import os
import shutil
import subprocess
import glob
import tempfile
from PySide6.QtWidgets import QMessageBox, QTextEdit, QInputDialog, QFileDialog, QVBoxLayout, QLabel, QListWidget, \
    QPushButton, QWidget, QHBoxLayout
from PySide6.QtCore import QCoreApplication, QProcess

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
        dialog = LoadConfigDialog()
        config_files = [f for f in os.listdir(USERS_CONFIG_DIR) if f.endswith(".py")]
        dialog.list_widget.addItems([os.path.splitext(f)[0] for f in config_files])

        if dialog.exec():
            selected_config = dialog.get_selected_config()
            self.config_path = os.path.join(USERS_CONFIG_DIR, f"{selected_config}.py")
            if self.ui.editor:
                self.ui.scroll_area.takeWidget()
                self.ui.editor.deleteLater()
                self.ui.editor = None
            self.ui.editor = ConfigEditor(self.config_path)
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
                path = os.path.join(USERS_CONFIG_DIR, f"{config_name}.py")
                self.ui.editor.save_config(path)

    def _create_remote_temp_script(self, scp_command, ssh_command):
        """Creates a temporary shell script to run a remote command."""
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh', encoding='utf-8') as f:
                f.write("#!/bin/bash\n")
                f.write("set -e\n")  # Exit on error
                f.write(f"{scp_command}\n")
                f.write(f"{ssh_command}\n")
                temp_script_path = f.name
            os.chmod(temp_script_path, 0o755)
            return temp_script_path
        except Exception as e:
            QMessageBox.critical(self.ui, "Error", f"Failed to create temporary script for remote execution: {e}")
            return None

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
            self.ui.log_output.append("NOTE: Viewing outputs directly from the UI is not supported for remote runs.")
            try:
                user_host, remote_path = openram_path.split(':', 1)
                user, host = user_host.split('@', 1)
            except ValueError:
                QMessageBox.critical(self.ui, "Error", "Invalid remote path format. Use user@host:/path/to/openram")
                self.ui.run_button.setEnabled(True)
                self.ui.run_button.setText("Run OpenRAM")
                return

            remote_temp_config_name = os.path.basename(self.config_path)
            remote_temp_config_path = f"/tmp/{remote_temp_config_name}"
            sram_compiler_script = os.path.join(remote_path, "sram_compiler.py")

            remote_command = f"""
                cd {remote_path} && \
                source openram_env/bin/activate && \
                source miniconda/bin/activate && \
                source setpaths.sh && \
                python3 -u {sram_compiler_script} {remote_temp_config_path} && \
                rm {remote_temp_config_path}
            """
            
            scp_command = f"scp -o BatchMode=yes {self.config_path} {user}@{host}:{remote_temp_config_path}"
            ssh_command = f"ssh -o BatchMode=yes {user}@{host} '{remote_command}'"

            self.temp_script_path = self._create_remote_temp_script(scp_command, ssh_command)
            if not self.temp_script_path:
                self.ui.run_button.setEnabled(True)
                self.ui.run_button.setText("Run OpenRAM")
                return

            self.process = QProcess()
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.on_output_ready)
            self.process.finished.connect(self.on_run_finished)
            self.process.start("bash", [self.temp_script_path])

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
            self.process.finished.connect(self.on_run_finished)
            self.process.start("bash", [self.temp_script_path])

    def on_output_ready(self):
        output = self.process.readAllStandardOutput().data().decode(errors='replace')
        self.ui.log_output.append(output.strip())

    def on_run_finished(self, exitCode, exitStatus):
        self.ui.log_output.append(f"\nOpenRAM process finished.")
        self.ui.log_output.append(f"Exit Code: {exitCode}")
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

        if is_remote:
            self.ui.log_output.append("Remote OpenRAM path detected for viewing GDS.")
            self.ui.log_output.append("NOTE: This requires a working X11 forward connection for your SSH session.")
            try:
                user_host, remote_openram_path = openram_path.split(':', 1)
                user, host = user_host.split('@', 1)
            except ValueError:
                QMessageBox.critical(self.ui, "Error", "Invalid remote path format. Use user@host:/path/to/openram")
                return

            remote_output_path = os.path.join(remote_openram_path, output_path_from_config)
            
            list_gds_command = f"ssh -o BatchMode=yes {user}@{host} 'ls -1 {remote_output_path}/*.gds 2>/dev/null'"

            try:
                result = subprocess.run(list_gds_command, shell=True, capture_output=True, text=True, timeout=15)
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)
                
                gds_files_full_paths = result.stdout.strip().split('\n')
                gds_files_full_paths = [f for f in gds_files_full_paths if f]
            except Exception as e:
                error_msg = f"Could not list remote GDS files.\nCommand: {list_gds_command}\nError: {e}"
                if hasattr(e, 'stderr'):
                    error_msg += f"\nStderr: {e.stderr}"
                QMessageBox.warning(self.ui, "Warning", error_msg)
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
                remote_klayout_command = f"""
                    cd {remote_openram_path} && \
                    source openram_env/bin/activate && \
                    source miniconda/bin/activate && \
                    source setpaths.sh && \
                    klayout {remote_gds_file_path}
                """
                
                success = QProcess.startDetached("ssh", ["-o", "BatchMode=yes", "-X", f"{user}@{host}", remote_klayout_command])

                if not success:
                    QMessageBox.critical(self.ui, "Error", "Failed to start the remote klayout process via SSH.")
                else:
                    self.ui.log_output.append(f"Attempting to launch klayout on {host} for {os.path.basename(remote_gds_file_path)}...")

        else:  # Local execution
            gds_files = glob.glob(os.path.join(output_path_from_config, "*.gds"))

            if not gds_files:
                QMessageBox.warning(self.ui, "Warning", f"No GDS file found in {output_path_from_config}")
                return

            gds_file = None
            if len(gds_files) == 1:
                gds_file = gds_files[0]
            else:
                file_names = [os.path.basename(f) for f in gds_files]
                file_name, ok = QInputDialog.getItem(self.ui, "Select GDS File", "Multiple GDS files found...",
                                                     file_names, 0, False)
                if ok and file_name:
                    gds_file = os.path.join(output_path_from_config, file_name)

            if gds_file:
                command = f"klayout {gds_file}"
                temp_script_path = self._create_temp_script(command)
                if temp_script_path:
                    QProcess.startDetached("bash", [temp_script_path])

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
        user_host_for_download = ""

        if is_remote:
            try:
                user_host, remote_openram_path = openram_path.split(':', 1)
                user, host = user_host.split('@', 1)
                remote_output_path = os.path.join(remote_openram_path, output_path_from_config)
                source_path_for_download = remote_output_path
                user_host_for_download = user_host
            except ValueError:
                file_list.addItem("Invalid remote path format in advanced settings.")
                QMessageBox.critical(self.ui, "Error", "Invalid remote path format. Use user@host:/path/to/openram")
                return

            list_files_command = f"ssh -o BatchMode=yes {user_host} 'ls -F {remote_output_path} 2>/dev/null'"
            try:
                result = subprocess.run(list_files_command, shell=True, capture_output=True, text=True, timeout=15)
                if result.returncode == 0:
                    files = result.stdout.strip().split('\n')
                    file_list.addItems([f for f in files if f])
                else:
                    file_list.addItem(f"Could not list remote directory (or it's empty).")
                    file_list.addItem(f"Error: {result.stderr.strip()}")
            except Exception as e:
                file_list.addItem(f"Error listing remote files: {e}")

        else:  # Local execution
            source_path_for_download = output_path_from_config
            try:
                files = sorted(os.listdir(output_path_from_config))
                file_list.addItems(files)
            except FileNotFoundError:
                file_list.addItem("Output directory not found.")

        button_layout = QHBoxLayout()
        download_button = QPushButton("Download Output Folder")
        # Pass the necessary info for remote or local download
        download_button.clicked.connect(lambda: self.download_output_folder(source_path_for_download, user_host_for_download))
        button_layout.addWidget(download_button)

        view_gds_button = QPushButton("View GDS")
        view_gds_button.clicked.connect(self.view_gds)
        button_layout.addWidget(view_gds_button)
        
        layout.addLayout(button_layout)

        if self.ui.editor:
            self.ui.scroll_area.takeWidget()
            self.ui.editor.deleteLater()
            self.ui.editor = None

        self.ui.scroll_area.setWidget(output_widget)

    def download_output_folder(self, source_path, user_host=""):
        is_remote = bool(user_host)
        self.ui.log_output.append("\n--- Starting Download ---")
        self.ui.log_output.append(f"Source Path: {source_path}")
        self.ui.log_output.append(f"Is Remote: {is_remote}")
        if is_remote:
            self.ui.log_output.append(f"User@Host: {user_host}")

        suggested_name = os.path.basename(source_path.strip('/'))
        
        home_dir = str(Path.home())
        initial_dir = os.path.join(home_dir, "Downloads")
        if not os.path.isdir(initial_dir):
            initial_dir = home_dir
        self.ui.log_output.append(f"Suggested Initial Directory: {initial_dir}")

        selected_dir = QFileDialog.getExistingDirectory(self.ui, "Select Destination Folder", initial_dir)

        if not selected_dir:
            self.ui.log_output.append("Download cancelled by user.")
            return

        self.ui.log_output.append(f"User selected destination folder: {selected_dir}")
        destination = os.path.join(selected_dir, suggested_name)
        self.ui.log_output.append(f"Final destination path: {destination}")

        if os.path.exists(destination):
            self.ui.log_output.append("Destination path exists. Asking user to overwrite.")
            reply = QMessageBox.question(self.ui, "Destination Exists",
                                           f"The destination '{destination}' already exists. Do you want to overwrite it?",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.ui.log_output.append("User chose to overwrite.")
                try:
                    if os.path.isfile(destination):
                        os.remove(destination)
                    elif os.path.isdir(destination):
                        shutil.rmtree(destination)
                    self.ui.log_output.append("Successfully removed existing destination.")
                except Exception as e:
                    error_msg = f"Failed to remove existing destination: {e}"
                    self.ui.log_output.append(f"ERROR: {error_msg}")
                    QMessageBox.critical(self.ui, "Error", error_msg)
                    return
            else:
                self.ui.log_output.append("User chose not to overwrite. Download cancelled.")
                return

        try:
            if is_remote:
                self.ui.log_output.append(f"Executing remote download...")
                remote_source = f"{user_host}:{source_path}"
                scp_command = ["scp", "-o", "BatchMode=yes", "-r", remote_source, destination]
                self.ui.log_output.append(f"Running command: {' '.join(scp_command)}")
                QCoreApplication.processEvents()
                
                process = subprocess.run(scp_command, capture_output=True, text=True, check=True, timeout=300)
                
                self.ui.log_output.append(f"scp stdout:\n{process.stdout}")
                self.ui.log_output.append(f"scp stderr:\n{process.stderr}")
            else:
                self.ui.log_output.append(f"Executing local copy...")
                QCoreApplication.processEvents()
                shutil.copytree(source_path, destination)
            
            self.ui.log_output.append("Download completed successfully.")
            QMessageBox.information(self.ui, "Success", f"Output folder downloaded successfully to {destination}")

        except FileNotFoundError:
            error_msg = f"Source path not found: {source_path}"
            self.ui.log_output.append(f"ERROR: {error_msg}")
            QMessageBox.critical(self.ui, "Error", error_msg)
        except subprocess.CalledProcessError as e:
            error_message = f"Failed to download folder using scp.\n"
            error_message += f"Command: {' '.join(e.args)}\n"
            error_message += f"Return Code: {e.returncode}\n"
            error_message += f"Stdout: {e.stdout}\n"
            error_message += f"Stderr: {e.stderr}"
            self.ui.log_output.append(f"ERROR: {error_message}")
            QMessageBox.critical(self.ui, "Error", error_message)
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            self.ui.log_output.append(f"ERROR: {error_msg}")
            QMessageBox.critical(self.ui, "Error", error_msg)

    def show_advanced_settings(self):
        if self.ui.editor:
            self.ui.scroll_area.takeWidget()
            self.ui.editor.deleteLater()
            self.ui.editor = None

        self.ui.editor = AdvancedConfigEditor()
        self.ui.editor.setMinimumWidth(400)
        self.ui.scroll_area.setWidget(self.ui.editor)

    def _get_file_properties_as_string(self, folder_path: str) -> str:
        output = []
        path = Path(folder_path)

        if not path.exists() or not path.is_dir():
            return f"Path '{folder_path}' does not exist or is not a directory."

        for file in path.iterdir():
            if file.is_file():
                stats = file.stat()
                file_info = (
                    f"<br> Config: <b>{file.stem}, </b>"
                    # f"  Size: {stats.st_size} bytes\n"
                    f"  Last accessed: {time.ctime(stats.st_atime)}, "
                    f"  Last modified: {time.ctime(stats.st_mtime)}"
                    # f"  Metadata changed (ctime): {time.ctime(stats.st_ctime)}\n"
                )
                output.append(file_info)

        return "\n".join(output) if output else "No files found in the directory."

    def _get_file_properties_as_table(self, folder_path: str) -> str:
        output = []
        path = Path(folder_path)

        if not path.exists() or not path.is_dir():
            return f"Path '{folder_path}' does not exist or is not a directory."

        # Table header
        header = f"{'Name':<30} {'Last Accessed':<25} {'Last Modified':<25}"
        separator = "-" * len(header)
        output.append(header)
        output.append(separator)

        for file in path.iterdir():
            if file.is_file():
                stats = file.stat()
                name = file.stem
                accessed = time.ctime(stats.st_atime)
                modified = time.ctime(stats.st_mtime)
                row = f"{name:<30} {accessed:<25} {modified:<25}"
                output.append(row)

        return "\n".join(output) if output else "No files found in the directory."

    def _get_file_properties_as_table(self, folder_path: str) -> str:
        path = Path(folder_path)

        if not path.exists() or not path.is_dir():
            return f"<p>Path '{folder_path}' does not exist or is not a directory.</p>"

        output = [
            "<table border='1' cellpadding='5' cellspacing='0'>",
            "<tr><th>Config Name</th><th>Last Accessed</th><th>Last Modified</th></tr>"
        ]

        for file in path.iterdir():
            if file.is_file():
                stats = file.stat()
                name = file.stem
                accessed = time.ctime(stats.st_atime)
                modified = time.ctime(stats.st_mtime)
                row = f"<tr><td>{name}</td><td>{accessed}</td><td>{modified}</td></tr>"
                output.append(row)

        output.append("</table>")
        return "\n".join(output)

    def _get_file_properties_as_table(self, folder_path: str) -> str:
        path = Path(folder_path)

        if not path.exists() or not path.is_dir():
            return f"<p>Path '{folder_path}' does not exist or is not a directory.</p>"

        # Gather all files with access time
        files = []
        for file in path.iterdir():
            if file.is_file():
                stats = file.stat()
                files.append({
                    "name": file.stem,
                    "accessed": stats.st_atime,
                    "modified": stats.st_mtime
                })

        # Sort by access time, descending, and take the last 3 accessed files
        recent_files = sorted(files, key=lambda x: x["accessed"], reverse=True)[:3]

        # Build HTML table
        output = [
            "<table border='1' cellpadding='5' cellspacing='0'>",
            "<tr><th>Config Name</th><th>Last Accessed</th><th>Last Modified</th></tr>"
        ]

        for file in recent_files:
            accessed = time.ctime(file["accessed"])
            modified = time.ctime(file["modified"])
            row = f"<tr><td>{file['name']}</td><td>{accessed}</td><td>{modified}</td></tr>"
            output.append(row)

        output.append("</table>")
        return "\n".join(output)

    def show_home_screen(self):
        if self.ui.editor:
            self.ui.scroll_area.takeWidget()
            self.ui.editor.deleteLater()
            self.ui.editor = None

        home_text_edit = QTextEdit()
        home_text_edit.setReadOnly(True)
        # home_content = HOME_SCREEN_MESSAGE
        # home_content = "<br><br><b>--- Recent Activity ---</b><br>" + self._get_file_properties_as_table(USERS_CONFIG_DIR)
        home_content = "<br><b> Recent Activity </b><br>" + self._get_file_properties_as_table(USERS_CONFIG_DIR)

        advanced_config_content = ""
        try:
            advanced_config = _load_config_file(ADVANCED_CONFIG_FILE)
            advanced_config_content = "<br><br><b>--- Current Advanced Settings ---</b><br>"
            for key, value in advanced_config.items():
                advanced_config_content += f"{key} = {value}<br>"
        except FileNotFoundError:
            advanced_config_content = "\n\nAdvanced config file not found."
        except Exception as e:
            advanced_config_content = f"\n\nError loading advanced config: {e}"

        home_text_edit.setHtml(home_content + advanced_config_content)
        self.ui.scroll_area.setWidget(home_text_edit)
