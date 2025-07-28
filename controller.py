import os
import subprocess
import glob
import tempfile
from PySide6.QtWidgets import QMessageBox, QTextEdit, QInputDialog
from PySide6.QtCore import QCoreApplication
from config_loader import _load_config_file
from config_editor import ConfigEditor
from advanced_config_editor import AdvancedConfigEditor
from constants import MANDATORY_CONFIG_KEYS, ADVANCED_CONFIG_FILE, HOME_SCREEN_MESSAGE, USERS_CONFIG_DIR
from dialogs import LoadConfigDialog, SaveConfigDialog

class Controller:
    def __init__(self, ui):
        self.ui = ui
        self.config = {}
        self.config_path = None

    import tempfile

    def _run_command_in_openram_env(self, command_to_run, capture_output=True):
        advanced_config = _load_config_file(ADVANCED_CONFIG_FILE)
        openram_path = advanced_config.get("openram_path")

        if not openram_path:
            QMessageBox.critical(self.ui, "Error", "OpenRAM path not set in advanced settings.")
            return None, None

        openram_activate_script = os.path.join(openram_path, "openram_env", "bin", "activate")
        miniconda_activate_script = os.path.join(openram_path, "miniconda", "bin", "activate")
        setpaths_script = os.path.join(openram_path, "setpaths.sh")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as f:
            f.write(f"#!/bin/bash\n")
            f.write(f"source {openram_activate_script}\n")
            f.write(f"source {miniconda_activate_script}\n")
            f.write(f"source {setpaths_script}\n")
            f.write(f"{command_to_run}\n")
            temp_script_path = f.name
        
        os.chmod(temp_script_path, 0o755)

        self.ui.log_output.append(f"Executing command: {command_to_run}\n")
        QCoreApplication.processEvents()

        if capture_output:
            process = subprocess.Popen([temp_script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            process = subprocess.Popen([temp_script_path])
            
        return process, temp_script_path

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
        if not self.config_path:
            QMessageBox.warning(self.ui, "Warning", "Please load a config file first.")
            return

        if not self.ui.editor or not hasattr(self.ui.editor, 'get_config'):
            current_config = _load_config_file(self.config_path)
        else:
            current_config = self.ui.editor.get_config()

        missing_fields = [field for field in MANDATORY_CONFIG_KEYS if not current_config.get(field)]
        if missing_fields:
            QMessageBox.critical(self.ui, "Error", f"Missing mandatory fields: {', '.join(missing_fields)}")
            return

        self.ui.run_button.setEnabled(False)
        self.ui.run_button.setText("Running...")
        self.ui.log_output.clear()
        self.ui.log_output.append("Running OpenRAM... please wait, this may take a while.")
        QCoreApplication.processEvents()

        #todo run in thread
        sram_compiler_script = os.path.join(_load_config_file(ADVANCED_CONFIG_FILE).get("openram_path"), "sram_compiler.py")
        command_to_run = f"python {sram_compiler_script} {self.config_path}"

        process, command = self._run_command_in_openram_env(command_to_run, capture_output=True)

        if process is None:
            self.ui.run_button.setEnabled(True)
            self.ui.run_button.setText("Run OpenRAM")
            return

        while True:
            output = process.stdout.readline().decode()
            if output == '' and process.poll() is not None:
                break
            if output:
                self.ui.log_output.append(output.strip())
                QCoreApplication.processEvents()
        
        rc = process.poll()
        if rc != 0:
            self.ui.log_output.append(f"OpenRAM failed with exit code {rc}")
            self.ui.log_output.append(process.stderr.read().decode())
        else:
            self.ui.log_output.append("OpenRAM process completed successfully.")

        self.ui.run_button.setEnabled(True)
        self.ui.run_button.setText("Run OpenRAM")

    def view_gds(self):
        if not self.config_path:
            QMessageBox.warning(self.ui, "Warning", "Please load a config file first.")
            return

        config = _load_config_file(self.config_path)
        output_path = config.get("output_path", ".")

        gds_files = glob.glob(os.path.join(output_path, "*.gds"))

        if not gds_files:
            QMessageBox.warning(self.ui, "Warning", f"No GDS file found in {output_path}")
            return

        gds_file = None,
        if len(gds_files) == 1:
            gds_file = gds_files[0]
        else:
            file_names = [os.path.basename(f) for f in gds_files]
            file_name, ok = QInputDialog.getItem(self.ui, "Select GDS File", "Multiple GDS files found. Please select one to open:", file_names, 0, False)
            if ok and file_name:
                gds_file = os.path.join(output_path, file_name)

        if gds_file:
            command = f"klayout {gds_file}"
            process, _ = self._run_command_in_openram_env(command, capture_output=False)

    def show_advanced_settings(self):
        if self.ui.editor:
            self.ui.scroll_area.takeWidget()
            self.ui.editor.deleteLater()
            self.ui.editor = None

        self.ui.editor = AdvancedConfigEditor()
        self.ui.editor.setMinimumWidth(400)
        self.ui.scroll_area.setWidget(self.ui.editor)

    def show_home_screen(self):
        if self.ui.editor:
            self.ui.scroll_area.takeWidget()
            self.ui.editor.deleteLater()
            self.ui.editor = None

        home_text_edit = QTextEdit()
        home_text_edit.setReadOnly(True)

        home_content = HOME_SCREEN_MESSAGE

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
