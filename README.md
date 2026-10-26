# Gestures:
- Thumb -> **move left**
- Thumb + Index finger -> **move right**
- Thumb, Index and Middle finger -> **move up**
- Thumb, Index, Middle and Ring finger -> **move down**
- All 5 finger up -> **move forward**
- Touching index and thumb with other finger up 👌 -> **move backwards**
- Index and middle finger pointing down -> **land**

**Follow Mode:**
- Only pinky pointing up -> 'attach' to the hand and keep it in frame by automatically following
*Failsafe during follow mode:*
If hand is no longer detected stop movement descend slowly and deactivate

## Workspace setup

Each contributor should create their own Python virtual environment locally. Do not
commit the `.venv` directory or other machine-specific files.

### Create and activate the environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate it with:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell says that running scripts is disabled, allow scripts only in the
current PowerShell session, then activate the environment:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

This does not change the machine-wide execution policy; the setting goes away
when you close that PowerShell window. Alternatively, skip activation and use
the environment's Python executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then install the shared project dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The dependency file should contain only packages required by this project. Do not
add machine-specific editable paths or the output of a full `pip freeze` unless
the team has agreed to maintain a platform-specific lock file.

Verify the selected environment with:

```bash
python -c "import cv2; import djitellopy; print('environment OK')"
```

In VS Code, use **Python: Select Interpreter** and choose the interpreter inside
`.venv`.

Before committing, check that local files are ignored:

```bash
git status
git check-ignore -v .venv/ .env __pycache__/
```

Commit `requirements.txt`, but keep `.venv/`, `.env`, `__pycache__/`, and other
local or generated files untracked.
