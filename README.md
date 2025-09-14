# Real-Time Process Manager

A production-quality, cross-platform system resource monitor and task manager built with Python, PySide6, psutil, and pyqtgraph.

![Screenshot](https://i.imgur.com/gK6yM9G.png)
*(Note: A representative screenshot would go here in a real project repository.)*

## Features

- **Real-Time Monitoring**: Live updates of system resource usage.
- **Comprehensive Metrics**:
  - **CPU**: Total and per-core usage (%), physical/logical core count.
  - **RAM**: Total, used, and available memory (GB and %).
  - **GPU**: Per-GPU usage, memory consumption (if NVIDIA GPU is present).
  - **Processes**: Detailed list of running processes (PID, Name, CPU%, RAM%, GPU%, Memory, Command).
- **Interactive UI**:
  - **Tabbed Interface**: Cleanly separated sections for Overview, Per-Core CPU, GPU, and Processes.
  - **Live Charts**: Sparkline-style charts showing recent history for key metrics.
  - **Process Management**: Sort, search, and filter the process list.
  - **Kill Process**: Right-click to terminate a selected process (with confirmation).
  - **Responsive Design**: The UI adapts to window resizing.
- **Efficient & Lightweight**:
  - Uses a background thread for data polling to keep the GUI responsive.
  - Configurable refresh interval (default: 1.5 seconds).
- **Cross-Platform**:
  - Works on Windows, macOS, and Linux.
  - GPU monitoring is supported for **NVIDIA GPUs only** via `pynvml`. The application gracefully handles systems without a supported GPU.

## Requirements

- Python 3.8+
- PySide6 (for the GUI)
- psutil (for system information)
- pyqtgraph (for live charts)
- pynvml (for NVIDIA GPU monitoring)

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd process_manager
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv .venv
    # On Windows
    source .venv/Scripts/activate
    # On macOS/Linux
    source .venv/bin/activate
    ```

3.  **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```

## How to Run

Execute the `main.py` script:

```bash
python main.py
```

### Privileges & Permissions

- On **macOS and some Linux systems**, the application may not be able to retrieve detailed information (like the full command path) for processes owned by other users unless it is run with elevated privileges (e.g., using `sudo`).
- On **Windows**, running as an administrator can provide more stable access to process information.

## Packaging for Distribution (Optional)

You can create a standalone executable using **PyInstaller**.

1.  **Install PyInstaller:**
    ```bash
    pip install pyinstaller
    ```

2.  **Build the executable:**
    ```bash
    pyinstaller --onefile --windowed --name "ProcessManager" main.py
    ```
    The final executable will be located in the `dist` folder.

## Testing

A small test suite is included to verify the core data collection logic (without involving the GUI).

To run the tests:
```bash
python -m unittest discover tests
```
