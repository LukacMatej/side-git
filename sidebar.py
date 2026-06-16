#!/usr/bin/env python3
import os

from git import InvalidGitRepositoryError, Repo
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class NotificationBanner(Static):
    """A full-width alert banner that matches the exact dimensions of the sidebar."""

    CSS = """
    NotificationBanner {
        display: none; /* Hidden by default */
        width: 100%;
        padding: 0 1;
        margin-top: 1;
        text-align: center;
    }
    """

    def show_alert(self, message: str, severity: str = "success") -> None:
        # Match colors to severity state
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
        self.styles.display = "block"  # Make visible

        # Automatically clear banner after 3 seconds
        self.set_timer(3.0, self.clear_alert)

    def clear_alert(self) -> None:
        self.styles.display = "none"


class CommitModal(ModalScreen[str]):
    """Floating pop-up window for entering commit messages safely."""

    CSS = """
    CommitModal {
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

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Static("[bold yellow]💬 ENTER COMMIT MESSAGE:[/bold yellow]")
            yield Input(placeholder="Type message here...", id="commit-input")
            yield Static("[gray]Press Enter to Confirm • Esc to Cancel[/gray]")

    def on_mount(self) -> None:
        self.query_one("#commit-input", Input).focus()

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

            # Safe branch handling even during detached HEAD states
            if repo.head.is_detached:
                branch_name = (
                    f"[yellow]Detached HEAD ({repo.head.commit.hexsha[:7]})[/yellow]"
                )
            else:
                branch_name = repo.active_branch.name

            untracked = repo.untracked_files
            modified = [item.a_path for item in repo.index.diff(None)]
            staged = [item.a_path for item in repo.index.diff("HEAD")]

            status_str = f"[bold cyan]🌿 BRANCH:[/bold cyan] {branch_name}\n"

            # 1. Staged Files
            status_str += "\n[bold green]✓ STAGED TO BE COMMITTED:[/bold green]\n"
            if staged:
                for f in staged[:3]:
                    status_str += f"  [green]+ {f}[/green]\n"
                if len(staged) > 3:
                    status_str += f"  ... and {len(staged) - 3} more\n"
            else:
                status_str += "  [gray](None)[/gray]\n"

            # 2. Unstaged changes
            status_str += "\n[bold red]⚠️ UNSTAGED CHANGES:[/bold red]\n"
            total_unstaged = modified + untracked
            if total_unstaged:
                for f in total_unstaged[:3]:
                    prefix = "?" if f in untracked else f"[bold]M[/bold]"
                    status_str += f"  [red]{prefix} {f}[/red]\n"
                if len(total_unstaged) > 3:
                    status_str += f"  ... and {len(total_unstaged) - 3} more\n"
            else:
                status_str += "  [green](Workspace clean)[/green]\n"

            # NEW: 3. Unpushed local commits tracking validation
            status_str += "\n[bold yellow]🚀 UNPUSHED LOCAL COMMITS:[/bold yellow]\n"
            try:
                if not repo.head.is_detached:
                    local_branch = repo.active_branch
                    upstream = local_branch.tracking_branch()
                    if upstream:
                        # Find commits present locally but missing upstream
                        unpushed_commits = list(
                            repo.iter_commits(f"{upstream.name}..{local_branch.name}")
                        )
                        if unpushed_commits:
                            for c in unpushed_commits[:3]:
                                status_str += f"  [yellow]↑ {c.hexsha[:7]}[/yellow] - {c.summary}\n"
                            if len(unpushed_commits) > 3:
                                status_str += (
                                    f"  ... and {len(unpushed_commits) - 3} more\n"
                                )
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

            # 4. Control Guide Layout
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
        layout: vertical;
    }
    GitSidebar {
        height: 1fr; /* Let status text take maximum remaining room */
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
    ]

    def compose(self) -> ComposeResult:
        self.git_widget = GitSidebar()
        self.notifier = NotificationBanner()
        with Container(id="main-layout"):
            yield self.git_widget
            yield self.notifier

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
        """[C] Opens the pop-up modal input box securely."""
        try:
            repo = self.get_repo()
            if not repo.index.diff("HEAD"):
                self.notifier.show_alert("Nothing staged! Press 'A' first.", "warning")
                return
            self.push_screen(CommitModal(), self.handle_commit_response)
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


if __name__ == "__main__":
    SidebarApp().run()
