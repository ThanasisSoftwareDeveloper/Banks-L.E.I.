# LEI Enricher (Desktop)

Batch-validate and enrich **LEI** codes from **Excel / LibreOffice Calc** using the **GLEIF API** (with optional fallback), and write results back into adjacent columns.

---

## Why this app exists

Teams doing **KYC/AML**, compliance, or vendor validation often maintain long spreadsheets with LEIs.  
Checking each LEI manually to confirm **Entity Status = ACTIVE** and capture **Next Renewal Date** is repetitive, slow, and easy to mess up.

This tool exists to turn that manual process into a **repeatable batch run**.

---

## What it does

- Reads LEIs from an **Excel/Calc** sheet
- Queries **GLEIF first**
- Optionally uses a **fallback provider for misses**
- Writes results back to the file into **neighboring columns**, e.g.:
  - **Entity Status**
  - **Next Renewal Date**
  - (optionally) other metadata depending on your configuration

---

## How it improves the workflow

Compared to manual lookups or one-off scripts, it provides:

- **GUI-driven batch processing** (no “one by one” checking)
- **Consistent output columns** (clean spreadsheet result)
- **Optional fallback for misses** (better coverage)
- **Rate-limit / anti-blocking friendly behavior** for large lists (delays/retries/backoff)

**Typical outcome:** hours of repetitive checking → a predictable run that updates the spreadsheet automatically.

---

## Quickstart

### Prerequisites
- Windows 10/11  
- Python **3.10+** (recommended **3.11+**)

### Install (PowerShell) for developers

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

### Run (for developers)
```powershell
lei-enricher
```

If the console command isn’t available, try:
```powershell
python -m lei_enricher
```
---
## Build & Release (Windows)

This project provides a desktop GUI app that enriches LEI records from Excel/Calc files.
Below are the exact steps to generate:
- a **portable app** (`Bank_LEI.exe`), and
- a **user-friendly installer** (**Next → Next → Finish**) for non-expert users.

> **Important:** Use **Command Prompt (CMD)** in VS Code Terminal for these steps (PowerShell may freeze on some setups).

---

### Stage 1 — Prepare the build environment (CMD + venv)

**Where:** VS Code → **Terminal → New Terminal** → select **Command Prompt (CMD)**  
**Project folder:** `C:\Projects\Bank_lei`

```bat
cd /d C:\Projects\Bank_lei
.\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install pyinstaller
```
### Stage 2 — Build the app executable (PyInstaller, one-folder)
- 2.1 Create an entry launcher (required for packaging)

Create this file in the project root:
File: run_bank_lei.py
```bat
from lei_enricher.main import main

if __name__ == "__main__":
    main()
```
- 2.2 Build (one-folder) 
```bat
pyinstaller --noconsole --name Bank_LEI run_bank_lei.py
```
Output (portable app):
dist\Bank_LEI\Bank_LEI.exe

Quick test: double-click dist\Bank_LEI\Bank_LEI.exe

### Stage 3 — Create the installer (Inno Setup: Next/Next/Finish)
- 3.1 Create the Inno Setup script

Create this file in the project root:
File: installer.iss

(The script copies everything from dist\Bank_LEI\* into {Program Files}\Bank LEI and creates shortcuts.)
```bat
#define MyAppName "Bank LEI"
#define MyAppExeName "Bank_LEI.exe"
#define MyAppPublisher "Bank LEI Team"
#define MyAppVersion "0.1.0"

[Setup]
AppId={{B3A1B6E1-4A2E-4F25-9F50-9A2A6F0B1C01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=Bank_LEI_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
; Optional Greek UI (only if Greek.isl exists on your system)
; Name: "greek"; MessagesFile: "compiler:Languages\Greek.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\Bank_LEI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
```
- 3.2 Compile the installer

Install Inno Setup 6.x

Open Inno Setup Compiler

File → Open → select installer.iss

Click Compile

Output (installer for non-technical users):

installer_output\Bank_LEI_Setup_0.1.0.exe

Distribute this installer to employees. They can install the app via Next → Next → Finish and run it from Start Menu/Desktop shortcut.

## Outputs summary

- Portable app (for quick testing): dist\Bank_LEI\Bank_LEI.exe

- Installer (recommended for end users): installer_output\Bank_LEI_Setup_0.1.0.exe
---
### Using the app (GUI)

- Select your Excel/Calc file

- Choose the sheet (if prompted) and the LEI column

- Click Start

- The app writes output into the next columns (Status / Renewal Date / etc.)

---
### “Enable fallback for misses” — when to use

Enable it only if you want extra coverage when:

- GLEIF returns no result for some LEIs, or

- you have datasets with occasional formatting/provider edge cases

If GLEIF already resolves everything you care about, keep it off (simpler + fewer requests).

---
### Project structure

- src/lei_enricher/ — application source code

- tests/ — tests

- pyproject.toml — packaging + dependencies

- .gitignore — excludes local/temporary files

Note: Do not commit .venv/ or .pytest_cache/ (local environment + cache).

---
### Troubleshooting

If PowerShell blocks activation, run:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

If installs fail, confirm Python is in PATH and rerun:
```powershell
python -m pip install --upgrade pip
```
---
### License

This project is licensed under the **GPLv3** License — see the **LICENSE** file for details.
