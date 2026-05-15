# AI Hallucination Juror - Judge Setup

This guide is tuned for the current repo and current implementation. It is the fastest path to get a judge from zero to a working demo.

## Fastest Install

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/Arnav2580/agentx/main/install.sh | bash
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/Arnav2580/agentx/main/install.ps1 | iex
```

The installer will:

- clone the project into `~/.juror-app`
- install Python dependencies
- ask for a Gemini API key
- create the `juror` command
- install the bundled VS Code extension if `code` is available

## What The Judge Should See First

Start the app:

```bash
juror start
```

Then open:

```text
http://localhost:8000
```

That page is the live dashboard and refreshes automatically.

## Chrome Extension

Chrome cannot be installed silently, so this is still manual:

1. Open `chrome://extensions`
2. Enable Developer Mode
3. Click Load Unpacked
4. Select the repo's `chrome-extension/` folder
5. Pin the extension if convenient

### What works in Chrome

- known AI sites auto-scan when a response finishes
- any page can be scanned manually
- a floating `JUROR` pill stays visible in the bottom-right corner
- `Ctrl+Shift+J` scans selected text or the latest detected AI response

### Good test path

1. Open Claude, ChatGPT, Gemini, Perplexity, or another supported AI site
2. Ask a technical question
3. Wait for the response to finish
4. The sidebar should open with the verdict

Manual fallback:

1. Select any text on any page
2. Press `Ctrl+Shift+J`
3. The sidebar opens and verifies the selected text

## VS Code Extension

If the installer found the `code` command, the extension should already be installed.

If not, install it manually:

```bash
code --install-extension ~/.juror-app/vscode-extension/ai-hallucination-juror-1.0.0.vsix --force
```

On Windows:

```powershell
code --install-extension $env:USERPROFILE\.juror-app\vscode-extension\ai-hallucination-juror-1.0.0.vsix --force
```

### What works in VS Code

- activity bar Juror panel
- verify current file
- verify selected text
- verdict sidebar with agent details
- optional auto-verify on save

### Good test path

1. Open a file with AI-generated text
2. Select the text
3. Right-click
4. Choose `Juror: Verify Selected Text`
5. Watch the sidebar render the verdict

## Terminal Flow

You can also demo it entirely from the terminal:

```bash
juror run claude "write a structural load calculation for Zone IV India"
juror verify tests/demo_scenarios/software_dev.py
juror history
```

## Demo Scenarios

These are the safest repeatable demos in the repo:

```bash
python tests/demo_scenarios/civil_engineering.py
python tests/demo_scenarios/financial_modeling.py
python tests/demo_scenarios/software_dev.py
python tests/demo_scenarios/healthcare.py
```

Expected results:

| Scenario | Expected verdict |
|---|---|
| `civil_engineering.py` | `BLOCKED` |
| `financial_modeling.py` | `FLAGGED` |
| `software_dev.py` | `BLOCKED` |
| `healthcare.py` | `BLOCKED` |

## Verdict Meaning

| Verdict | Meaning | What to tell the judge |
|---|---|---|
| `APPROVED` | 0-1 jury failures | The output looks safe enough to proceed |
| `FLAGGED` | 2 jury failures | The output may be usable, but it needs review |
| `BLOCKED` | 3-5 jury failures | The output is unsafe; a corrected version is shown |

## Troubleshooting

| Problem | Fix |
|---|---|
| Server will not start | Run `pip install -r requirements.txt` and try again |
| Dashboard does not load | Check `http://localhost:8000/health` |
| Chrome sidebar not visible | Click the floating `JUROR` button or use `Ctrl+Shift+J` |
| Chrome shows server error | Start the backend with `juror start` |
| VS Code sidebar is empty | Verify selected text or current file once |
| VS Code install command fails | Make sure the `code` command is available in PATH |
| API key issues | Recreate `~/.juror/.env` with a valid `GEMINI_API_KEY` |

## Files Judges Usually Need

- repo root installer: `install.sh` or `install.ps1`
- Chrome folder: `chrome-extension/`
- VS Code package: `vscode-extension/ai-hallucination-juror-1.0.0.vsix`
- dashboard: `http://localhost:8000`

