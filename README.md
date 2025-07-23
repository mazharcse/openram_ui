# OpenRAM UI

A PySide6-based desktop application for loading, editing, and running OpenRAM configurations.

---

## 🚀 Features

-   **Load & Edit:** Load any OpenRAM-compatible Python config file and edit parameters through a user-friendly UI.
-   **Save:** Save modified configurations to new files.
-   **Run OpenRAM:** Execute OpenRAM directly from the GUI and view the output logs.
-   **View GDS:** Open generated GDS files in an external viewer like KLayout.
-   **Modular Design:** The UI and application logic are separated for better maintainability.

---

## 📦 Requirements

-   Python 3.8+
-   PySide6
-   KLayout (for viewing GDS files)

---

## 🛠️ Installation

1.  **Clone the project**:

    ```bash
    git clone https://github.com/mazharcse/openram_ui.git
    cd openram_ui
    ```

2.  **Install dependencies**:

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Run the App**:
    ```bash
    python3 main.py
    ```

---

## 🗂️ Project Structure

```
openram_ui/
├── main.py                # Main application entry point
├── ui.py                  # Defines the UI layout and widgets
├── methods.py             # Contains the application logic and event handlers
├── config_loader.py       # Loads Python-based OpenRAM config files
├── config_editor.py       # Editable form for the config values
├── default.py             # Sample OpenRAM config
├── requirements.txt
└── README.md
```

---

## 🧩 Sample Config Format (`default.py`)

```python
word_size = 4
num_words = 16
words_per_row = 1
num_spare_cols = 1
num_spare_rows = 1
tech_name = "sky130"
process_corners = ["TT"]
supply_voltages = [1.8]
temperatures = [25]
output_path = "output_16x4"
use_simulation = False
```

---

## 📌 Next Steps (Planned Features)

-   Run OpenRAM
-   View GDS output
-   Advanced settings editor
-   Upload and validate PDK files



