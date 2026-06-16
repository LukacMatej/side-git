#!/usr/bin/env python3
import os

from git import InvalidGitRepositoryError, Repo
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen  # Imported for popup window support
from textual.widgets import Input, Static


class CommitModal(ModalScreen[str]):
    """A floating popup window for entering commit messages securely."""

    CSS = """
    CommitModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6); /* Dim background behind the popup */
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

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Static("[bold yellow]💬 ENTER COMMIT MESSAGE:[/bold yellow]")
            yield Input(placeholder="Type message here...", id="commit-input")
            yield Static("[gray]Press Enter to Confirm • Esc to Cancel[/gray]")

    def on_mount(self) -> None:
        # Automatically focus the input field the millisecond the popup appears
        self.query_one("#commit-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Triggered when user presses Enter inside the input box."""
        self.dismiss(event.value.strip())

    def on_key(self, event) -> None:
        """Listen for the Escape key to close without saving."""
        if event.key == "escape":
            self.dismiss("")


class GitSidebar(Static):
    def update_status(self) -> None:
        """Fetch Git status details and render the UI text."""
        try:
            repo = Repo(os.getcwd(), search_parent_directories=True)
            branch = repo.active_branch.name

            untracked = repo.untracked_files
            modified = [item.a_path for item in repo.index.diff(None)]
            staged = [item.a_path for item in repo.index.diff("HEAD")]

            status_str = f"[bold cyan]🌿 BRANCH:[/bold cyan] {branch}\n"

            status_str += "\n[bold green]✓ STAGED TO BE COMMITTED:[/bold green]\n"
            if staged:
                for f in staged[:5]:
                    status_str += f"  [green]+ {f}[/green]\n"
                if len(staged) > 5:
                    status_str += f"  ... and {len(staged) - 5} more\n"
            else:
                status_str += "  [gray](None)[/gray]\n"

            status_str += "\n[bold red]⚠️ UNSTAGED CHANGES:[/bold red]\n"
            total_unstaged = modified + untracked
            if total_unstaged:
                for f in total_unstaged[:5]:
                    prefix = "?" if f in untracked else "M"
                    status_str += f"  [red]{prefix} {f}[/red]\n"
                if len(total_unstaged) > 5:
                    status_str += f"  ... and {len(total_unstaged) - 5} more\n"
            else:
                status_str += "  [green](Workspace clean)[/green]\n"

            status_str += (
                f"\n[bold magenta]⌨️ KEYBOARD CONTROLS:[/bold magenta]\n"
                f"-----------------------------------\n"
                f"[bold]\[C][/bold] Commit Staged   [bold]\[A][/bold] Stage All\n"
                f"[bold]\[S][/bold] Stash Changes   [bold]\[R][/bold] Refresh UI\n"
                f"[bold]\[P][/bold] Push (Origin)   [bold]\[L][/bold] Pull (Origin)\n"
                f"[bold]\[V][/bold] Revert HEAD     [bold]\[Q][/bold] Close Sidebar"
            )
            self.update(status_str)

        except InvalidGitRepositoryError:
            self.update(
                "[bold red]❌ Not a Git Repository[/bold red]\n\nPress [bold]\[Q][/bold] to exit."
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
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_status", "Refresh"),
        ("a", "stage_all", "Stage All"),
        ("c", "open_commit_modal", "Commit"),  # New hotkey for popup
        ("s", "stash_changes", "Stash"),
        ("p", "push_origin", "Push"),
        ("l", "pull_origin", "Pull"),
        ("v", "revert_head", "Revert HEAD"),
    ]

    def compose(self) -> ComposeResult:
        self.git_widget = GitSidebar()
        with Container(id="main-layout"):
            yield self.git_widget

    def get_repo(self):
        return Repo(os.getcwd(), search_parent_directories=True)

    def action_refresh_status(self) -> None:
        self.git_widget.update_status()

    def action_stage_all(self) -> None:
        try:
            repo = self.get_repo()
            repo.git.add(A=True)
            self.git_widget.update_status()
            self.notify("Staged all workspace changes.")
        except Exception as e:
            self.notify(f"Stage failed: {e}", severity="error")

    def action_open_commit_modal(self) -> None:
        """[C] Opens the popup window for the commit message."""
        try:
            repo = self.get_repo()
            if not repo.index.diff("HEAD"):
                self.notify(
                    "Nothing staged to commit! Press 'A' first.", severity="warning"
                )
                return

            # Show the popup, and pass a callback function to handle the result when it closes
            self.push_screen(CommitModal(), self.handle_commit_response)
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def handle_commit_response(self, commit_msg: str) -> None:
        """Processes the string returned by the popup box once dismissed."""
        if not commit_msg:
            self.notify("Commit canceled.")
            return

        try:
            repo = self.get_repo()
            repo.index.commit(commit_msg)
            self.git_widget.update_status()
            self.notify("Changes successfully committed!")
        except Exception as e:
            self.notify(f"Commit failed: {e}", severity="error")

    def action_stash_changes(self) -> None:
        try:
            repo = self.get_repo()
            repo.git.stash()
            self.git_widget.update_status()
            self.notify("Workspace pushed to stash stack.")
        except Exception as e:
            self.notify(f"Stash failed: {e}", severity="error")

    def action_push_origin(self) -> None:
        try:
            repo = self.get_repo()
            self.notify(f"Pushing to origin...")
            repo.remotes.origin.push()
            self.notify("Push completed!")
        except Exception as e:
            self.notify(f"Push failed: {e}", severity="error")

    def action_pull_origin(self) -> None:
        try:
            repo = self.get_repo()
            self.notify("Pulling from origin...")
            repo.remotes.origin.pull()
            self.git_widget.update_status()
            self.notify("Pull completed!")
        except Exception as e:
            self.notify(f"Pull failed: {e}", severity="error")

    def action_revert_head(self) -> None:
        try:
            repo = self.get_repo()
            repo.git.revert("HEAD", no_edit=True)
            self.git_widget.update_status()
            self.notify("Reverted last commit.")
        except Exception as e:
            self.notify(f"Revert failed: {e}", severity="error")


if __name__ == "__main__":
    SidebarApp().run()
