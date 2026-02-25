"""Create a desktop shortcut for Lyudochka (run once after installation)."""
import os
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(BASE_DIR, "icons", "shortcut_icon128.png")
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
SHORTCUT_PATH = os.path.join(DESKTOP, "Lyudochka.lnk")

ps_script = f"""
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{SHORTCUT_PATH}')
$Shortcut.TargetPath = 'pythonw.exe'
$Shortcut.Arguments = '"{MAIN_SCRIPT}"'
$Shortcut.WorkingDirectory = '{BASE_DIR}'
$Shortcut.IconLocation = '{ICON_PATH}'
$Shortcut.Save()
"""

subprocess.run(["powershell", "-Command", ps_script], check=True)
print(f"Ярлык создан: {SHORTCUT_PATH}")
