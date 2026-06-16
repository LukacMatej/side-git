#!/usr/bin/env python3
import os
import sys

# Get the absolute path to your sidebar script
# (Assuming sidebar.py is in the same folder as main.py)
script_dir = os.path.dirname(os.path.realpath(__file__))
sidebar_path = os.path.join(script_dir, "sidebar.py")

# Check if we are already sitting inside a tmux session
is_inside_tmux = "TMUX" in os.environ

if is_inside_tmux:
    # Scenario A: You are already in tmux. Just split the window!
    os.system(f"tmux split-window -h -l 35 'python3 {sidebar_path}'")
else:
    # Scenario B: You are in a normal shell.
    # Start a new tmux session and immediately split it to load the sidebar.
    os.system(f"tmux new-session \; split-window -h -l 35 'python3 {sidebar_path}'")
