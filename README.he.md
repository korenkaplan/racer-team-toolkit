Here is how to set up the **Top Language Switcher** for your repository.

Create a second file named **`README.he.md`** in your repository root, and update the tops of both files as shown below.

---

### File 1: `README.md` (English Version)

```markdown
# 🏁 Racer Team Toolkit

🌐 **Language / שפה:** English | [עברית (Hebrew)](README.he.md)

---

Welcome to the **Racer Team Toolkit**! This internal utility bundles everyday Racer Team workflows—such as ADB commands, SSH tasks, file transfers, APK installations, and device resets—into one simple terminal application.

---

## 📚 Table of Contents
1. [Overview & Features](#overview--features)
2. [Project Architecture & Structure](#project-architecture--structure)
3. [Windows Installation & Setup](#windows-installation--setup)
4. [Windows Security Setup](#windows-security-setup)
5. [Development & Contributing](#development--contributing)

---

## Overview & Features

Instead of running separate scripts or command-line sequences manually, the toolkit provides an interactive menu driven by your arrow keys.

| Feature | Key Capabilities |
| --- | --- |
| **REFF & Video Extractor** | Pulls `.reff` logs and screen recordings, auto-corrects out-of-sync device timestamps (e.g., fixing `01_08_2024` back to current dates), and groups related files into flight folders on your Desktop. |
| **APK Installer** | Scans connected devices, matches appropriate APKs from your `Downloads` folder, displays a pre-installation plan, and handles bulk installs. |
| **JAR Management** | Establishes SSH connections to manage the remote **Racer Groundlord** application (restart service or deploy updated JARs). |
| **Folders Reset** | Clears accumulated test data (`REFF` files and screen videos) across all connected devices using Quick Reset or target-specific Custom Reset. |

---

## Project Architecture & Structure

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
├── README.md            # English documentation
└── README.he.md         # Hebrew documentation

```

### Adding a New Module

To add a tool named `log_extractor`:

1. Create a folder: `src/racer_team_toolkit/log_extractor/` containing `main.py` (UI flow) and `functions.py` (logic).
2. Register the device configurations in `config.py` if needed.
3. Import and route your new module inside `src/racer_team_toolkit/main.py`.

---

## Windows Installation & Setup

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

## Windows Security Setup

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

## Development & Contributing

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

```

---

### File 2: `README.he.md` (Hebrew Version)

<div dir="rtl">

```markdown
# 🏁 ערכת הכלים של צוות Racer

🌐 **Language / שפה:** [English (אנגלית)](README.md) | עברית

---

ברוכים הבאים ל-**Racer Team Toolkit**! כלי פנימי המאחד תהליכי עבודה נפוצים של צוות Racer — כגון פקודות ADB, משימות SSH, העברת קבצים, התקנת APK ואיפוס מכשירים — לאפליקציית טרמינל נוחה אחת.

---

## 📚 תוכן עניינים
1. [סקירה ותכונות מרכזיות](#-סקירה-ותכונות-מרכזיות)
2. [ארכיטקטורת הפרויקט ומבנה](#-ארכיטקטורת-הפרויקט-ומבנה)
3. [התקנה והפעלה ב-Windows](#-התקנה-והפעלה-ב-windows)
4. [הגדרות אבטחה ב-Windows](#-הגדרות-אבטחה-ב-windows)
5. [פיתוח ותרומה לקוד](#-פיתוח-ותרומה-לקוד)

---

## 🚀 סקירה ותכונות מרכזיות

במקום להריץ סקריפטים או פקודות ידניות בנפרד, ערכת הכלים מספקת תפריט אינטראקטיבי המוצג בטרמינל ומופעל באמצעות מקשי החצים.

| תכונה | יכולות מרכזיות |
| --- | --- |
| **REFF & Video Extractor** | חילוץ קבצי `.reff` והקלטות מסך, תיקון אוטומטי של חותמות זמן שגויות במכשירים (למשל תיקון תאריך `01_08_2024` לתאריך הנוכחי), וקיבוץ הקבצים לפי טיסות לתיקייה בשולחן העבודה. |
| **APK Installer** | זיהוי מכשירים מחוברים, התאמת קבצי ה-APK המתאימים מתיקיית `Downloads`, הצגת תוכנית התקנה מראש, וביצוע התקנה מרוכזת. |
| **JAR Management** | התחברות ב-SSH לניהול אפליקציית **Racer Groundlord** המרוחקת (הפעלה מחדש או העלאת קובץ JAR מעודכן). |
| **Folders Reset** | ניקוי נתוני בדיקה קודמים (קבצי `REFF` והקלטות מסך) מכל המכשירים המחוברים באמצעות Quick Reset או Custom Reset לפי מכשיר. |

---

## 🏗️ ארכיטקטורת הפרויקט ומבנה

הקוד בנוי בצורה מודולרית כך שניתן להוסיף כלים פנימיים חדשים מבלי לשנות תכונות קיימות.

### מבנה התיקיות

```text
racer-team-toolkit/
├── .github/workflows/   # תהליך בנייה אוטומטי של EXE ל-Windows
├── src/racer_team_toolkit/
│   ├── main.py          # נקודת הכניסה לאפליקציה וניתוח התפריט
│   ├── config.py        # רישום מכשירים מרכזי והגדרות גלובליות
│   ├── adb/             # פונקציות ADB מרכזיות וקבצים מובנים
│   ├── ui/              # רכיבי טרמינל משותפים (טבלאות, תפריטים, ספינרים)
│   ├── reff_extractor/  # לוגיקת חילוץ REFF ותיקון זמנים
│   ├── apk_installer/   # התאמת APK למכשיר והתקנה
│   ├── jar_management/  # תפעול SSH מרוחק באמצעות Paramiko
│   └── quick_reset/     # לוגיקת איפוס וניקוי מכשירים
├── pyproject.toml       # הגדרות פרויקט ותלויות
├── README.md            # תיעוד באנגלית
└── README.he.md         # תיעוד בעברית

```

### הוספת מודול חדש

כדי להוסיף כלי חדש בשם `log_extractor`:

1. צור תיקייה: `src/racer_team_toolkit/log_extractor/` המכילה `main.py` (זרימת UI) ו-`functions.py` (לוגיקה).
2. רשום את הגדרות המכשירים ב-`config.py` במידת הצורך.
3. ייבא ונתב את המודול החדש בתוך `src/racer_team_toolkit/main.py`.

---

## 💻 התקנה והפעלה ב-Windows

האפליקציה בייצור ארוזה כ-**קובץ ריצה עצמאי ל-Windows** (`racer-team-toolkit.exe`) הכולל מראש את סביבת Python ו-Android Platform Tools. משתמשים **אינם** צריכים להתקין Python, `uv` או ADB מראש.

### איך להוריד

1. פתח את לשונית **Actions** במאגר ה-GitHub.
2. בחר בתהליך **Build Windows EXE**.
3. לחץ על הרצה המוצלחת האחרונה וגלול לחלק **Artifacts**.
4. הורד את `racer-team-toolkit-windows` וחץ את הקובץ `racer-team-toolkit.exe`.

### הרצת האפליקציה

לחץ דאבל-קליק על `racer-team-toolkit.exe` כדי לפתוח את התפריט האינטראקטיבי:

* **מקשי חצים:** מעבר בין אפשרויות.
* **רווח (Spacebar):** בחירה/ביטול פריטים בתפריטי בחירה מרובה.
* **Enter:** אישור ובחירה.

---

## 🛡️ הגדרות אבטחה ב-Windows

מכיוון שגרסאות פנימיות אינן חתומות דיגיטלית, Windows Defender או Smart App Control עשויים להציג התראה על הקובץ.

### ביטול חסימת קובץ ה-EXE

פתח את **PowerShell** והרץ את פקודת ה-Unblock עבור נתיב ההורדה שלך:

```powershell
Unblock-File -Path "$HOME\Downloads\racer-team-toolkit.exe"

```

### Smart App Control (אם הקובץ נחסם)

אם Smart App Control מונע את ההרצה ב-Windows 11:

1. פתח את **Windows Security** ← **App & browser control** ← **Smart App Control settings**.
2. שנה את ההגדרות בהתאם למדיניות האבטחה של הצוות. *(בתכנון העתידי מתוכננת חתימה דיגיטלית שתבטל צורך זה).*

---

## 🛠️ פיתוח ותרומה לקוד

### הגדרה מקומית

דרישות: **Python 3.12+** ו-**`uv`**.

```bash
# שכפול המאגר והתקנת תלויות
git clone <repository-url>
cd racer-team-toolkit
uv sync

# הרצה מקומית
uv run racer-team-toolkit

```

```

</div>

```