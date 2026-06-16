#!/usr/bin/env python3
import os

from git import InvalidGitRepositoryError, Repo
from textual.app import App, ComposeResult
from textual.containers import Container  # Imported container for click protection
from textual.widgets import Static


class GitSidebar(Static):
    def update_status(self) -> None:
        """Helper method to fetch and redraw Git details."""
        try:
            repo = Repo(os.getcwd(), search_parent_directories=True)
            branch = repo.active_branch.name

            if repo.is_dirty():
                untracked = len(repo.untracked_files)
                modified = len(repo.index.diff(None))
                status = (
                    f"[bold red]Modified ({modified} files, {untracked} new)[/bold red]"
                )
            else:
                status = "[bold green]Clean[/bold green]"

            self.update(
                f"[bold cyan]GIT STATUS[/bold cyan]\n"
                f"-------------------\n"
                f"[bold]Branch:[/bold] {branch}\n"
                f"[bold]State:[/bold] {status}\n\n"
                f"[bold magenta]CONTROLS:[/bold magenta]\n"
                f"-------------------\n"
                f"[bold]\[A][/bold] Stage All Files\n"
                f"[bold]\[R][/bold] Refresh Info\n"
                f"[bold]\[Q][/bold] Close Sidebar"
            )
        except InvalidGitRepositoryError:
            self.update(
                "[bold red]Not a Git Repository[/bold red]\n\n[bold]\[Q][/bold] Exit"
            )

    def on_mount(self) -> None:
        self.update_status()


class SidebarApp(App):
    # Shifted styling from 'Screen' to an explicit container layout ID
    CSS = """
    #main-layout {
        background: #181818;
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
    ]

    def compose(self) -> ComposeResult:
        self.git_widget = GitSidebar()
        # Wrapping in a layout container completely resolves the mouse click AssertionError bug
        with Container(id="main-layout"):
            yield self.git_widget

    def action_refresh_status(self) -> None:
        self.git_widget.update_status()

    def action_stage_all(self) -> None:
        try:
            repo = Repo(os.getcwd(), search_parent_directories=True)
            if repo.is_dirty() or repo.untracked_files:
                repo.git.add(A=True)
                self.git_widget.update_status()
                self.notify("Staged all changes!")
            else:
                self.notify("Nothing to stage.", severity="warning")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")


if __name__ == "__main__":
    SidebarApp().run()
