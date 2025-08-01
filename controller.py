import os
import subprocess
import glob
import tempfile
from PySide6.QtWidgets import QMessageBox, QTextEdit, QInputDialog
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

        sram_compiler_script = os.path.join(_load_config_file(ADVANCED_CONFIG_FILE).get("openram_path"), "sram_compiler.py")
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
        output_path = config.get(OUTPUT_PATH, ".")
        gds_files = glob.glob(os.path.join(output_path, "*.gds"))

        if not gds_files:
            QMessageBox.warning(self.ui, "Warning", f"No GDS file found in {output_path}")
            return

        gds_file = None
        if len(gds_files) == 1:
            gds_file = gds_files[0]
        else:
            file_names = [os.path.basename(f) for f in gds_files]
            file_name, ok = QInputDialog.getItem(self.ui, "Select GDS File", "Multiple GDS files found...", file_names, 0, False)
            if ok and file_name:
                gds_file = os.path.join(output_path, file_name)

        if gds_file:
            command = f"klayout {gds_file}"
            temp_script_path = self._create_temp_script(command)
            if temp_script_path:
                # Use startDetached for a "fire-and-forget" GUI application like klayout.
                # The temporary script will not be deleted by this process, which is acceptable.
                QProcess.startDetached("bash", [temp_script_path])

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
            "<tr><th>Name</th><th>Last Accessed</th><th>Last Modified</th></tr>"
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
            "<tr><th>Name</th><th>Last Accessed</th><th>Last Modified</th></tr>"
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
        home_content = "<br><b> Recent Activity </b><br>" +self._get_file_properties_as_table(USERS_CONFIG_DIR)
        
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