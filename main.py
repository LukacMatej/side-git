#!/usr/bin/env python3
"""
gitsidebar - a small Git status sidebar for Konsole.

Run with no arguments: tries to split the current Konsole window and
launch the sidebar in the new right-hand pane. If that's not possible
(not inside Konsole, qdbus missing, D-Bus call rejected, etc.) it just
falls back to running the sidebar directly in the current terminal, so
the binary still does *something* useful no matter where it's run from.

Run with `--sidebar`: skip the split logic and just run the TUI. This is
what the script passes to itself when re-launching in the new pane, so
the new pane doesn't try to split again.
"""

import os
import shutil
import subprocess
import sys
import time

from git import InvalidGitRepositoryError, Repo
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Static


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


# --------------------------------------------------------------------------
# TUI widgets (unchanged behavior from the original sidebar.py)
# --------------------------------------------------------------------------


class NotificationBanner(Static):
    """A full-width alert banner that matches the exact dimensions of the sidebar."""

    CSS = """
    NotificationBanner {
        display: none;
        width: 100%;
        padding: 0 1;
        margin-top: 1;
        text-align: center;
    }
    """

    def show_alert(self, message: str, severity: str = "success") -> None:
        colors = {
            "success": ("#00cc66", "black"),
            "info": ("#00bcff", "black"),
            "warning": ("#ffb300", "black"),
            "error": ("#ff3333", "white"),
        }
        bg, fg = colors.get(severity, colors["info"])

        self.update(f"[bold]{message}[/bold]")
        self.styles.background = bg
        self.styles.color = fg
        self.styles.display = "block"

        self.set_timer(3.0, self.clear_alert)

    def clear_alert(self) -> None:
        self.styles.display = "none"


class InputModal(ModalScreen[str]):
    """A reusable popup window that handles all text input workflows dynamically."""

    CSS = """
    InputModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #modal-box {
        width: 90%;
        height: auto;
        background: #222222;
        border: solid #00bcff;
        padding: 1 2;
    }
    #modal-box Input {
        background: #141414;
        color: white;
        border: solid #444444;
        margin: 1 0;
    }
    """

    def __init__(self, title: str, placeholder: str):
        super().__init__()
        self.title_text = title
        self.placeholder_text = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Static(f"[bold yellow]\U0001f4ac {self.title_text}:[/bold yellow]")
            yield Input(placeholder=self.placeholder_text, id="modal-input")
            yield Static("[gray]Press Enter to Confirm \u2022 Esc to Cancel[/gray]")

    def on_mount(self) -> None:
        self.query_one("#modal-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss("")


class GitSidebar(Static):
    def update_status(self) -> None:
        """Fetch Git details and draw the interactive layouts."""
        try:
            repo = Repo(os.getcwd(), search_parent_directories=True)

            if repo.head.is_detached:
                active_branch_name = f"Detached HEAD ({repo.head.commit.hexsha[:7]})"
            else:
                active_branch_name = repo.active_branch.name

            untracked = repo.untracked_files
            modified_diff = list(repo.index.diff(None))
            staged_diff = list(repo.index.diff("HEAD"))

            def describe(item):
                """Return (letter, label) using the real change_type
                (M/A/D/R/C/T) instead of assuming everything is modified."""
                ct = item.change_type or "M"
                if (
                    ct == "R"
                    and item.a_path
                    and item.b_path
                    and item.a_path != item.b_path
                ):
                    return ct, f"{item.a_path} -> {item.b_path}"
                return ct, (item.b_path or item.a_path)

            status_str = f"[bold cyan]\U0001f33f ACTIVE BRANCH:[/bold cyan] [bold white]{active_branch_name}[/bold white]\n"
            status_str += "\n[bold magenta]\u2728 LOCAL BRANCHES:[/bold magenta]\n"
            try:
                for b in repo.branches:
                    if b.name == active_branch_name:
                        status_str += f"  [bold #00bcff]* {b.name}[/bold #00bcff] [gray](current)[/gray]\n"
                    else:
                        status_str += f"    {b.name}\n"
            except Exception:
                status_str += "  [gray](Unable to list branches)[/gray]\n"

            status_str += "\n[bold green]\u2713 STAGED TO BE COMMITTED:[/bold green]\n"
            if staged_diff:
                for item in staged_diff:
                    letter, label = describe(item)
                    status_str += f"  [green]{letter} {label}[/green]\n"
            else:
                status_str += "  [gray](None)[/gray]\n"

            status_str += "\n[bold red]\u26a0\ufe0f UNSTAGED CHANGES:[/bold red]\n"
            unstaged_entries = [describe(item) for item in modified_diff]
            unstaged_entries += [("?", path) for path in untracked]
            if unstaged_entries:
                for letter, label in unstaged_entries:
                    status_str += f"  [red]{letter} {label}[/red]\n"
            else:
                status_str += "  [green](Workspace clean)[/green]\n"

            status_str += (
                "\n[bold yellow]\U0001f680 UNPUSHED LOCAL COMMITS:[/bold yellow]\n"
            )
            try:
                if not repo.head.is_detached:
                    local_branch = repo.active_branch
                    upstream = local_branch.tracking_branch()
                    if upstream:
                        unpushed_commits = list(
                            repo.iter_commits(f"{upstream.name}..{local_branch.name}")
                        )
                        if unpushed_commits:
                            for c in unpushed_commits:
                                status_str += f"  [yellow]^ {c.hexsha[:7]}[/yellow] - {c.summary}\n"
                        else:
                            status_str += (
                                "  [green](All sync'd with remote origin)[/green]\n"
                            )
                    else:
                        status_str += "  [orange3]Branch not tracking remote upstream.[/orange3]\n"
                else:
                    status_str += "  [gray]Unavailable in detached HEAD state.[/gray]\n"
            except Exception:
                status_str += "  [gray](Unable to parse remote logs)[/gray]\n"

            status_str += (
                "\n[bold magenta]\u2328\ufe0f WORKSPACE:[/bold magenta]      [bold magenta]\U0001f33f BRANCHES:[/bold magenta]\n"
                "------------------  -------------------\n"
                "[bold]\\[A][/bold] Stage All\n[bold]\\[B][/bold] New Branch\n"
                "[bold]\\[C][/bold] Commit Staged\n[bold]\\[O][/bold] Checkout Branch\n"
                "[bold]\\[S][/bold] Stash Changes\n[bold]\\[X][/bold] Delete Branch\n"
                "[bold]\\[P][/bold] Push Origin\n[bold]\\[L][/bold] Pull Origin\n"
                "[bold]\\[V][/bold] Revert HEAD\n[bold]\\[R][/bold] Refresh UI\n"
                "[bold]\\[Q][/bold] Close Sidebar"
            )
            self.update(status_str)

        except InvalidGitRepositoryError:
            self.update(
                "[bold red]\u274c Not a Git Repository[/bold red]\n\nPress [bold]\\[Q][/bold] to exit."
            )

    def on_mount(self) -> None:
        self.update_status()


class SidebarApp(App):
    CSS = """
    #main-layout {
        background: #141414;
        color: #dcdcdc;
        padding: 1 2;
        width: 100%;
        height: 100%;
        layout: vertical;
    }
    #status-scroll {
        height: 1fr;
    }
    GitSidebar {
        height: auto;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_status", "Refresh"),
        ("a", "stage_all", "Stage All"),
        ("c", "open_commit_modal", "Commit"),
        ("s", "stash_changes", "Stash"),
        ("p", "push_origin", "Push"),
        ("l", "pull_origin", "Pull"),
        ("v", "revert_head", "Revert HEAD"),
        ("b", "open_new_branch_modal", "New Branch"),
        ("o", "open_checkout_modal", "Checkout Branch"),
        ("x", "open_delete_branch_modal", "Delete Branch"),
    ]

    def compose(self) -> ComposeResult:
        self.git_widget = GitSidebar()
        self.notifier = NotificationBanner()
        with Container(id="main-layout"):
            with VerticalScroll(id="status-scroll"):
                yield self.git_widget
            yield self.notifier

    def on_mount(self) -> None:
        # Keep the panel live even if nothing is pressed - e.g. you edit
        # or commit from the other pane and want the sidebar to catch up.
        self.set_interval(2.0, self.git_widget.update_status)

    def get_repo(self):
        return Repo(os.getcwd(), search_parent_directories=True)

    def action_refresh_status(self) -> None:
        self.git_widget.update_status()
        self.notifier.show_alert("Status Refreshed", "info")

    def action_stage_all(self) -> None:
        try:
            repo = self.get_repo()
            repo.git.add(A=True)
            self.git_widget.update_status()
            self.notifier.show_alert("Staged all changes!", "success")
        except Exception as e:
            self.notifier.show_alert(f"Stage failed: {e}", "error")

    def action_open_commit_modal(self) -> None:
        try:
            repo = self.get_repo()
            if not repo.index.diff("HEAD"):
                self.notifier.show_alert("Nothing staged! Press 'A' first.", "warning")
                return
            self.push_screen(
                InputModal("ENTER COMMIT MESSAGE", "Type message here..."),
                self.handle_commit_response,
            )
        except Exception as e:
            self.notifier.show_alert(f"Error: {e}", "error")

    def handle_commit_response(self, commit_msg: str) -> None:
        if not commit_msg:
            self.notifier.show_alert("Commit canceled.", "info")
            return
        try:
            repo = self.get_repo()
            repo.index.commit(commit_msg)
            self.git_widget.update_status()
            self.notifier.show_alert("Changes committed locally!", "success")
        except Exception as e:
            self.notifier.show_alert(f"Commit failed: {e}", "error")

    def action_open_new_branch_modal(self) -> None:
        self.push_screen(
            InputModal("CREATE & SWITCH TO NEW BRANCH", "Enter new branch name..."),
            self.handle_new_branch,
        )

    def handle_new_branch(self, name: str) -> None:
        if not name:
            return
        try:
            repo = self.get_repo()
            repo.git.checkout("-b", name)
        except Exception as e:
            self.notifier.show_alert(f"Failed to create branch: {e}", "error")
            return

        self.git_widget.update_status()

        try:
            repo.git.push("--set-upstream", "origin", name)
            self.notifier.show_alert(
                f"Created '{name}' and tracking origin/{name}", "success"
            )
        except Exception as e:
            self.notifier.show_alert(
                f"Branch '{name}' created locally, but push --set-upstream failed: {e}",
                "warning",
            )

        self.git_widget.update_status()

    def action_open_checkout_modal(self) -> None:
        self.push_screen(
            InputModal("CHECKOUT EXISTING BRANCH", "Enter branch name..."),
            self.handle_checkout,
        )

    def handle_checkout(self, name: str) -> None:
        if not name:
            return
        try:
            repo = self.get_repo()
            repo.git.checkout(name)
            self.git_widget.update_status()
            self.notifier.show_alert(f"Switched to branch: {name}", "success")
        except Exception as e:
            self.notifier.show_alert(f"Checkout failed: {name} not found?", "error")

    def action_open_delete_branch_modal(self) -> None:
        self.push_screen(
            InputModal("DELETE LOCAL BRANCH", "Enter branch name to remove..."),
            self.handle_delete_branch,
        )

    def handle_delete_branch(self, name: str) -> None:
        if not name:
            return
        try:
            repo = self.get_repo()
            repo.git.branch("-d", name)
            self.git_widget.update_status()
            self.notifier.show_alert(f"Deleted branch: {name}", "success")
        except Exception as e:
            self.notifier.show_alert(f"Deletion failed: {e}", "error")

    def action_stash_changes(self) -> None:
        try:
            repo = self.get_repo()
            repo.git.stash()
            self.git_widget.update_status()
            self.notifier.show_alert("Changes saved to stash stack.", "success")
        except Exception as e:
            self.notifier.show_alert(f"Stash failed: {e}", "error")

    def action_push_origin(self) -> None:
        try:
            repo = self.get_repo()
            self.notifier.show_alert("Pushing to remote repository...", "info")
            repo.remotes.origin.push()
            self.git_widget.update_status()
            self.notifier.show_alert("Push completed successfully!", "success")
        except Exception as e:
            self.notifier.show_alert(f"Push failed: {e}", "error")

    def action_pull_origin(self) -> None:
        try:
            repo = self.get_repo()
            self.notifier.show_alert("Pulling remote modifications...", "info")
            repo.remotes.origin.pull()
            self.git_widget.update_status()
            self.notifier.show_alert("Pull sync complete!", "success")
        except Exception as e:
            self.notifier.show_alert(f"Pull failed: {e}", "error")

    def action_revert_head(self) -> None:
        try:
            repo = self.get_repo()
            repo.git.revert("HEAD", no_edit=True)
            self.git_widget.update_status()
            self.notifier.show_alert("Reverted previous commit.", "success")
        except Exception as e:
            self.notifier.show_alert(f"Revert failed: {e}", "error")


# --------------------------------------------------------------------------
# Launcher logic: split the Konsole window and relaunch this same binary
# in the new pane with --sidebar. Falls back to running in place on failure.
# --------------------------------------------------------------------------


def get_dbus_command():
    for cmd in ["qdbus-qt6", "qdbus6", "qdbus"]:
        if shutil.which(cmd):
            return cmd
    return None


def get_self_invocation(extra_args: str = "") -> str:
    """Return a shell-ready command string that re-runs this same program."""
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller binary: sys.executable IS this program.
        base = f'"{sys.executable}"'
    else:
        # Running as a plain .py script: re-invoke with the same interpreter.
        base = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
    return f"{base} {extra_args}".strip()


def run_dbus(args, label):
    """Run a qdbus call, returning stdout on success or None (with a
    printed reason) on failure. Never silently swallows errors."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5)
    except FileNotFoundError:
        eprint(f"[gitsidebar] {label}: '{args[0]}' not found")
        return None
    except subprocess.TimeoutExpired:
        eprint(f"[gitsidebar] {label}: timed out")
        return None

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        eprint(f"[gitsidebar] {label} failed (exit {result.returncode}): {detail}")
        return None

    return result.stdout.strip()


def try_konsole_split() -> bool:
    """Attempt to split the current Konsole window and run the sidebar
    in the new pane. Returns True on success, False if anything failed
    (in which case the caller should fall back to running in place)."""

    dbus_cmd = get_dbus_command()
    konsole_service = os.environ.get("KONSOLE_DBUS_SERVICE")
    konsole_window = os.environ.get("KONSOLE_DBUS_WINDOW", "/Windows/1")

    if not dbus_cmd:
        eprint(
            "[gitsidebar] qdbus not found (install qt6-tools / qttools). Running inline instead."
        )
        return False

    if not konsole_service:
        eprint(
            "[gitsidebar] Not inside a Konsole D-Bus session. Running inline instead."
        )
        return False

    if (
        run_dbus(
            [
                dbus_cmd,
                konsole_service,
                "/konsole/MainWindow_1",
                "org.kde.KMainWindow.activateAction",
                "split-view-left-right",
            ],
            "split-view-left-right",
        )
        is None
    ):
        return False

    time.sleep(0.15)

    for _ in range(8):
        run_dbus(
            [
                dbus_cmd,
                konsole_service,
                "/konsole/MainWindow_1",
                "org.kde.KMainWindow.activateAction",
                "shrink-active-view",
            ],
            "shrink-active-view",
        )

    session_id = run_dbus(
        [
            dbus_cmd,
            konsole_service,
            konsole_window,
            "org.kde.konsole.Window.currentSession",
        ],
        "currentSession",
    )
    if not session_id:
        return False

    session_path = (
        session_id if session_id.startswith("/Sessions/") else f"/Sessions/{session_id}"
    )
    command = f"{get_self_invocation('--sidebar')}; exit"

    if (
        run_dbus(
            [
                dbus_cmd,
                konsole_service,
                session_path,
                "org.kde.konsole.Session.runCommand",
                command,
            ],
            "runCommand",
        )
        is None
    ):
        eprint(
            "[gitsidebar] runCommand was rejected. In Konsole, check "
            "Settings > Configure Notifications, or whether security-sensitive "
            "D-Bus methods are disabled for this profile, then try again."
        )
        return False

    return True


def main() -> None:
    if "--sidebar" in sys.argv[1:]:
        SidebarApp().run()
        return

    if try_konsole_split():
        return

    # Not in Konsole, qdbus missing, or the split failed for some reason:
    # just run the sidebar right here instead of doing nothing.
    SidebarApp().run()


if __name__ == "__main__":
    main()
