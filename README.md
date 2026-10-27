# Gestures mode:
- Index up -> **move left**
- Index + middle finger up -> **move right**
- Index, Middle and ring finger up -> **move up**
- Index, Middle, Ring and pinky up finger -> **move down**
- index, ring, pinky up, middle down -> **move forward**
- Index, middle, pinky up, ring down -> **move backwards**
- index down, middle, ring and pinky up -> **land**
- thumbs up -> **standby**
- If hand is not detected -> wait 30 seconds before landing

**Follow Mode:**
- Only pinky pointing up -> 'attach' to the hand and keep it in frame by automatically following
*Failsafe during follow mode:*
If hand is no longer detected stop movement descend slowly and deactivate

**Mediapipe hand landmarks diagram:**
![alt text](hand_landmarks.png)

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

## Run gesture recognition with the Tello camera (dry-run)

This connects to the Tello, starts its video stream, and runs gesture recognition
on the drone camera feed. Recognized
commands are printed to the terminal only; no takeoff or movement commands are
sent to the drone. Takeoff is disabled. Follow mode is recognized but does not
control flight yet.

1. Power on the Tello and connect your computer to the drone's Wi-Fi network.
2. Run this from the repository root:

   ```powershell
   .\.venv\Scripts\python.exe droneControl.py
   ```

Press **Q** in the video window to quit. If the connection fails, confirm that
your computer is connected to the Tello's Wi-Fi and try again.

Before committing, check that local files are ignored:

```bash
git status
git check-ignore -v .venv/ .env __pycache__/
```

Commit `requirements.txt`, but keep `.venv/`, `.env`, `__pycache__/`, and other
local or generated files untracked.
