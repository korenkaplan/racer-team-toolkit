# 🏁 Racer Team Toolkit

Welcome to the **Racer Team Toolkit**! This internal utility bundles everyday Racer Team workflows—such as ADB commands, SSH tasks, file transfers, APK installations, and device resets—into one simple terminal application.

---

## 📚 Table of Contents

1. [Overview & Features](https://www.google.com/search?q=%23-overview--features)
2. [Project Architecture & Structure](https://www.google.com/search?q=%23-project-architecture--structure)
3. [Windows Installation & Setup](https://www.google.com/search?q=%23-windows-installation--setup)
4. [Windows Security Setup](https://www.google.com/search?q=%23-windows-security-setup)
5. [Development & Contributing](https://www.google.com/search?q=%23-development--contributing)

---

## 🚀 Overview & Features

Instead of running separate scripts or command-line sequences manually, the toolkit provides an interactive menu driven by your arrow keys.

| Feature | Key Capabilities |
| --- | --- |
| **REFF & Video Extractor** | Pulls `.reff` logs and screen recordings, auto-corrects out-of-sync device timestamps (e.g., fixing `01_08_2024` back to current dates), and groups related files into flight folders on your Desktop. |
| **APK Installer** | Scans connected devices, matches appropriate APKs from your `Downloads` folder, displays a pre-installation plan, and handles bulk installs. |
| **JAR Management** | Establishes SSH connections to manage the remote **Racer Groundlord** application (restart service or deploy updated JARs). |
| **Folders Reset** | Clears accumulated test data (`REFF` files and screen videos) across all connected devices using Quick Reset or target-specific Custom Reset. |

---

## 🏗️ Project Architecture & Structure

The codebase is designed so new internal tools can be added without modifying existing features.

### Directory Layout

```text
racer-team-toolkit/
├── .github/workflows/   # Automated Windows EXE build workflow
├── src/racer_team_toolkit/
│   ├── main.py          # Application entry point & menu router
│   ├── config.py        # Central device registry & global settings
│   ├── adb/             # Centralized ADB functions & bundled binaries
│   ├── ui/              # Shared terminal tables, menus, & spinners
│   ├── reff_extractor/  # REFF extraction & time correction logic
│   ├── apk_installer/   # Device-to-APK matching & installation
│   ├── jar_management/  # Remote SSH operations via Paramiko
│   └── quick_reset/     # Device cleanup logic
├── pyproject.toml       # Project configuration & dependencies
└── README.md

```

### Adding a New Module

To add a tool named `log_extractor`:

1. Create a folder: `src/racer_team_toolkit/log_extractor/` containing `main.py` (UI flow) and `functions.py` (logic).
2. Register the device configurations in `config.py` if needed.
3. Import and route your new module inside `src/racer_team_toolkit/main.py`.

---

## 💻 Windows Installation & Setup

The production application is packaged as a **standalone Windows executable** (`racer-team-toolkit.exe`) with Python runtime and Android Platform Tools pre-bundled. Users **do not** need to pre-install Python, `uv`, or ADB.

### How to Download

1. Open the **Actions** tab in the GitHub repository.
2. Select the **Build Windows EXE** workflow.
3. Click on the latest successful run and scroll to **Artifacts**.
4. Download `racer-team-toolkit-windows` and extract `racer-team-toolkit.exe`.

### Running the App

Double-click `racer-team-toolkit.exe` to launch the interactive terminal menu:

* **Arrow keys:** Move through options.
* **Spacebar:** Toggle items in multi-select menus.
* **Enter:** Confirm selection.

---

## 🛡️ Windows Security Setup

Because internal builds are unsigned, Windows Defender or Smart App Control may flag the downloaded `.exe`.

### Unblock the Executable

Run **PowerShell** and execute the unblock command for your download path:

```powershell
Unblock-File -Path "$HOME\Downloads\racer-team-toolkit.exe"

```

### Smart App Control (If Blocked)

If Smart App Control prevents execution on Windows 11:

1. Open **Windows Security** → **App & browser control** → **Smart App Control settings**.
2. Toggle settings as permitted by your team’s security guidelines. *(Long-term release plans include code-signing certificates to remove this step).*

---

## 🛠️ Development & Contributing

### Local Setup

Requirements: **Python 3.12+** and **`uv`**.

```bash
# Clone & install dependencies
git clone <repository-url>
cd racer-team-toolkit
uv sync

# Run locally
uv run racer-team-toolkit

```