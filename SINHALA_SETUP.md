# Sinhala Display Setup Instructions

## 1. Add Sinhala Input Method
1. Open **System Settings** → **Keyboard** → **Input Sources**
2. Click the **+** button
3. Search for **Sinhala** 
4. Select **Sinhala** and click **Add**

## 2. Configure VS Code for Sinhala Support

### Method A: Copy Settings (Recommended)
1. Press `Cmd + ,` to open VS Code settings
2. Click the **"Open Settings (JSON)"** icon in the top-right
3. Copy the contents from `vscode-sinhala-settings.json` in this project
4. Paste into your settings.json file
5. Save the file

### Method B: Manual Configuration
Add these settings to your VS Code settings.json:
```json
{
  "terminal.integrated.fontFamily": "Sinhala Sangam MN, SF Mono, Menlo, Monaco, 'Courier New', monospace",
  "terminal.integrated.fontSize": 13,
  "editor.fontFamily": "'Sinhala Sangam MN', 'SF Mono', 'Fira Code', Menlo, Monaco, 'Courier New', monospace"
}
```

## 3. Shell Configuration (Already Applied)
The following has been added to your ~/.zshrc:
```bash
export LANG=si_LK.UTF-8
export LC_ALL=si_LK.UTF-8
```

## 4. Test Sinhala Rendering
Run this command to test:
```bash
echo "සිංහල පරික්ෂණය"
```

## 5. Alternative Terminal (If Issues Persist)
If VS Code terminal still has issues:
1. Install **iTerm2** from https://iterm2.com/
2. Set the same font: iTerm2 → Preferences → Profiles → Text → Font → "Sinhala Sangam MN"
3. Run the speech-to-text script in iTerm2

## 6. Restart VS Code
After making changes, restart VS Code for full effect.

## Troubleshooting
- If characters appear broken, check that "Sinhala Sangam MN" font is installed
- For complex scripts, iTerm2 often provides better rendering than VS Code terminal
- Ensure terminal encoding is set to UTF-8

## Font Alternatives
If "Sinhala Sangam MN" doesn't work well:
- Noto Sans Sinhala
- Iskoola Pota  
- Malithi Web
