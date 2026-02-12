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

### Install (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```
---

### Run
```powershell
lei-enricher
```

If the console command isn’t available, try:
```powershell
python -m lei_enricher
```
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
