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
            yield Static(f"[bold yellow]💬 {self.title_text}:[/bold yellow]")
            yield Input(placeholder=self.placeholder_text, id="modal-input")
            yield Static("[gray]Press Enter to Confirm • Esc to Cancel[/gray]")

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
            modified = [item.a_path for item in repo.index.diff(None)]
            staged = [item.a_path for item in repo.index.diff("HEAD")]

            # --- 1. BRANCHES MANAGEMENT SECTION ---
            status_str = f"[bold cyan]🌿 ACTIVE BRANCH:[/bold cyan] [bold white]{active_branch_name}[/bold white]\n"
            status_str += "\n[bold magenta]✨ LOCAL BRANCHES:[/bold magenta]\n"
            try:
                for b in repo.branches:
                    if b.name == active_branch_name:
                        status_str += f"  [bold #00bcff]* {b.name}[/bold #00bcff] [gray](current)[/gray]\n"
                    else:
                        status_str += f"    {b.name}\n"
            except Exception:
                status_str += "  [gray](Unable to list branches)[/gray]\n"

            # --- 2. STAGED CHANGES ---
            status_str += "\n[bold green]✓ STAGED TO BE COMMITTED:[/bold green]\n"
            if staged:
                for f in staged[:3]:
                    status_str += f"  [green]+ {f}[/green]\n"
                if len(staged) > 3:
                    status_str += f"  ... and {len(staged) - 3} more\n"
            else:
                status_str += "  [gray](None)[/gray]\n"

            # --- 3. UNSTAGED CHANGES ---
            status_str += "\n[bold red]⚠️ UNSTAGED CHANGES:[/bold red]\n"
            total_unstaged = modified + untracked
            if total_unstaged:
                for f in total_unstaged[:3]:
                    prefix = "?" if f in untracked else "M"
                    status_str += f"  [red]{prefix} {f}[/red]\n"
                if len(total_unstaged) > 3:
                    status_str += f"  ... and {len(total_unstaged) - 3} more\n"
            else:
                status_str += "  [green](Workspace clean)[/green]\n"

            # --- 4. UNPUSHED LOGS ---
            status_str += "\n[bold yellow]🚀 UNPUSHED LOCAL COMMITS:[/bold yellow]\n"
            try:
                if not repo.head.is_detached:
                    local_branch = repo.active_branch
                    upstream = local_branch.tracking_branch()
                    if upstream:
                        unpushed_commits = list(
                            repo.iter_commits(f"{upstream.name}..{local_branch.name}")
                        )
                        if unpushed_commits:
                            for c in unpushed_commits[:2]:
                                status_str += f"  [yellow]↑ {c.hexsha[:7]}[/yellow] - {c.summary}\n"
                            if len(unpushed_commits) > 2:
                                status_str += (
                                    f"  ... and {len(unpushed_commits) - 2} more\n"
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

            # --- 5. COMPACT GUIDE LAYOUT ---
            status_str += (
                f"\n[bold magenta]⌨️ WORKSPACE:[/bold magenta]      [bold magenta]🌿 BRANCHES:[/bold magenta]\n"
                f"------------------  -------------------\n"
                f"[bold]\[A][/bold] Stage All\n[bold]\[B][/bold] New Branch\n"
                f"[bold]\[C][/bold] Commit Staged\n[bold]\[O][/bold] Checkout Branch\n"
                f"[bold]\[S][/bold] Stash Changes\n[bold]\[X][/bold] Delete Branch\n"
                f"[bold]\[P][/bold] Push Origin\n[bold]\[L][/bold] Pull Origin\n"
                f"[bold]\[V][/bold] Revert HEAD\n[bold]\[R][/bold] Refresh UI\n"
                f"[bold]\[Q][/bold] Close Sidebar"
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
        height: 1fr;
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
        # Added explicit branch management bindings
        ("b", "open_new_branch_modal", "New Branch"),
        ("o", "open_checkout_modal", "Checkout Branch"),
        ("x", "open_delete_branch_modal", "Delete Branch"),
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
        try:
            repo = self.get_repo()
            if not repo.index.diff("HEAD"):
                self.notifier.show_alert("Nothing staged! Press 'A' first.", "warning")
                return
            # Reusing the dynamic InputModal architecture for standard commits
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

    # --- NEW: BRANCH LOGIC METHODS ---

    def action_open_new_branch_modal(self) -> None:
        """[B] Request name for a brand new branch execution split."""
        self.push_screen(
            InputModal("CREATE & SWITCH TO NEW BRANCH", "Enter new branch name..."),
            self.handle_new_branch,
        )

    def handle_new_branch(self, name: str) -> None:
        if not name:
            return
        try:
            repo = self.get_repo()
            # Runs: git checkout -b <name>
            repo.git.checkout("-b", name)
            self.git_widget.update_status()
            self.notifier.show_alert(f"Switched to new branch: {name}", "success")
        except Exception as e:
            self.notifier.show_alert(f"Failed to create branch: {e}", "error")

    def action_open_checkout_modal(self) -> None:
        """[O] Request target destination branch checkout assignment."""
        self.push_screen(
            InputModal("CHECKOUT EXISTING BRANCH", "Enter branch name..."),
            self.handle_checkout,
        )

    def handle_checkout(self, name: str) -> None:
        if not name:
            return
        try:
            repo = self.get_repo()
            # Runs: git checkout <name>
            repo.git.checkout(name)
            self.git_widget.update_status()
            self.notifier.show_alert(f"Switched to branch: {name}", "success")
        except Exception as e:
            self.notifier.show_alert(f"Checkout failed: {name} not found?", "error")

    def action_open_delete_branch_modal(self) -> None:
        """[X] Request targets for standard local branch deletion cleanup."""
        self.push_screen(
            InputModal("DELETE LOCAL BRANCH", "Enter branch name to remove..."),
            self.handle_delete_branch,
        )

    def handle_delete_branch(self, name: str) -> None:
        if not name:
            return
        try:
            repo = self.get_repo()
            # Runs: git branch -d <name>
            repo.git.branch("-d", name)
            self.git_widget.update_status()
            self.notifier.show_alert(f"Deleted branch: {name}", "success")
        except Exception as e:
            self.notifier.show_alert(f"Deletion failed: {e}", "error")

    # --- BASIC GIT ACTIONS ---

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
