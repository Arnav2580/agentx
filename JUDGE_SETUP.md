# AI Hallucination Juror - Judge Setup (3 Minutes)

Works on Windows, macOS, and Linux.

---

## Step 1 - Start the Server

**Windows:**
```cmd
cd juror
pip install -r requirements.txt
python -m server.main
```

**macOS / Linux:**
```bash
cd juror
pip3 install -r requirements.txt
python3 -m server.main
```

Open **http://localhost:8000** - you should see the live dashboard.

---

## Step 2 - Install Chrome Extension (30 seconds)

1. Open **Google Chrome**
2. Go to `chrome://extensions`
3. Enable **Developer Mode** (toggle, top-right corner)
4. Click **Load Unpacked**
5. Select the `chrome-extension/` folder from this project
6. Pin the extension: click the puzzle icon -> pin **AI Hallucination Juror**

**Test it:**
- Open any AI site (Claude.ai, ChatGPT, Gemini, Perplexity, Grok...)
- Ask any technical question
- The Juror sidebar appears and scans the response automatically

**Works on ANY site:**
- Select any text on any page -> press **Ctrl+Shift+J** -> Juror scans it
- Or click the **SCAN** button in the sidebar

---

## Step 3 - Install VS Code Extension (30 seconds)

1. Open **VS Code**
2. Press `Ctrl+Shift+X` (Extensions panel)
3. Drag `ai-hallucination-juror-1.0.0.vsix` into the panel
4. Click **Install**
5. The **⬡ Juror** icon appears in the left activity bar

**Test it:**
- Open any file
- Select some AI-generated text
- Right-click -> **Juror: Verify Selected Text**
- Verdict appears in the sidebar panel

---

## Step 4 - Terminal (Optional)

```bash
# Wrap any AI CLI
juror run claude "write a structural load calculation for Zone IV India"

# Verify a file
juror verify path/to/file.py

# View verdict history
juror history
```

---

## What the Verdicts Mean

| Verdict | Agents Failed | Action |
|---|---|---|
| ✅ APPROVED | 0-1 | Output is safe - proceed normally |
| ⚠️ FLAGGED | 2 | Issues found - review warnings before using |
| 🚫 BLOCKED | 3-5 | Dangerous output - corrected version provided |

---

## Live Dashboard

**http://localhost:8000** - shows all verdicts in real time, auto-refreshes every 10 seconds.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Server won't start | `pip install -r requirements.txt` then retry |
| Chrome sidebar not appearing | Click the extension icon -> SCAN, or press Ctrl+Shift+J |
| VS Code sidebar empty | Right-click text -> Juror: Verify Selected Text |
| `ANTHROPIC_API_KEY` error | Ignore - system uses Gemini, not Anthropic |
| Slow first response (~3s) | Normal - 5 AI agents running in parallel |
