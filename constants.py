DEFAULT_CONFIG_FILE= "config/default.py"
ADVANCED_CONFIG_FILE = "config/advanced_config.py"
# MANDATORY_CONFIG_FILE = "config/mandatory_config.py"
USERS_CONFIG_DIR = "users_configs"

MANDATORY_CONFIG_KEYS = ["num_words", 
                         "word_size", 
                         "tech_name"]
ADVANCED_CONFIG_KEYS = ["openram_path", "pdk_name"]

HOME_SCREEN_MESSAGE = """A PySide6-based desktop application for loading, editing, and running OpenRAM configurations.<br><br>🚀 Features<br><br>- <b>Load & Edit:</b> Load any OpenRAM-compatible Python config file and edit parameters through a user-friendly UI.<br>- <b>Save:</b> Save modified configurations to new files.<br>- <b>Select PDK:</b> Select your own PDK.<br>- <b>Run OpenRAM:</b> Execute OpenRAM directly from the GUI and view the output logs.<br>- <b>View GDS:</b> Open generated GDS files in an external viewer like KLayout.<br>- <b>Modular Design:</b> The UI and application logic are separated for better maintainability.<br>"""
