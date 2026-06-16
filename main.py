#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import time


def get_dbus_command():
    for cmd in ["qdbus-qt6", "qdbus6", "qdbus"]:
        if shutil.which(cmd):
            return cmd
    return None


dbus_cmd = get_dbus_command()
konsole_service = os.environ.get("KONSOLE_DBUS_SERVICE")
konsole_window = os.environ.get("KONSOLE_DBUS_WINDOW", "/Windows/1")

if not dbus_cmd:
    print(
        "❌ Error: Missing system dependency. Please run: sudo dnf install qt6-qttools"
    )
elif not konsole_service:
    print(
        "❌ Error: This script must be run directly inside an active KDE Konsole window."
    )
else:
    # 1. Natively split the window vertically (Defaults to 50:50 distribution)
    subprocess.run(
        [
            dbus_cmd,
            konsole_service,
            "/konsole/MainWindow_1",
            "org.kde.KMainWindow.activateAction",
            "split-view-left-right",
        ]
    )

    # Give Konsole a tiny millisecond slice to parse the split layout
    time.sleep(0.1)

    # 2. Shift the split ratio from 50:50 to roughly 70:30
    # We call Konsole's 'shrink-active-view' command sequentially to slide the border rightward
    for _ in range(8):
        subprocess.run(
            [
                dbus_cmd,
                konsole_service,
                "/konsole/MainWindow_1",
                "org.kde.KMainWindow.activateAction",
                "shrink-active-view",
            ]
        )

    # 3. Locate the session ID assigned to the right-hand split pane
    result = subprocess.run(
        [dbus_cmd, konsole_service, konsole_window, "currentSession"],
        capture_output=True,
        text=True,
    )
    new_session_id = result.stdout.strip()

    session_path = (
        new_session_id
        if new_session_id.startswith("/Sessions/")
        else f"/Sessions/{new_session_id}"
    )

    # 4. Map paths and run your Python script under your active virtual environment
    script_dir = os.path.dirname(os.path.realpath(__file__))
    sidebar_path = os.path.join(script_dir, "sidebar.py")
    active_python = sys.executable

    subprocess.run(
        [
            dbus_cmd,
            konsole_service,
            session_path,
            "org.kde.konsole.Session.runCommand",
            f"{active_python} {sidebar_path}",
        ]
    )
