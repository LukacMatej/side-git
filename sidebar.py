#!/usr/bin/env python3
import os

from git import InvalidGitRepositoryError, Repo
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static


class GitSidebar(Static):
    def on_mount(self) -> None:
        try:
            repo = Repo(os.getcwd(), search_parent_directories=True)
            branch = repo.active_branch.name
            status = "Clean" if not repo.is_dirty() else "Modified"
            self.update(
                f"[bold cyan]GIT STATUS[/bold cyan]\n"
                f"-------------------\n"
                f"[bold]Branch:[/bold] {branch}\n"
                f"[bold]State:[/bold] {status}\n\n"
                f"[bold green]Controls:[/bold green]\n"
                f"[Q] Close Sidebar"
            )
        except InvalidGitRepositoryError:
            self.update("[bold red]Not a Git Repository[/bold red]")


class SidebarApp(App):
    CSS = """
    Screen {
        background: #1e1e1e;
        color: white;
        padding: 1 2;
    }
    """
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield GitSidebar()


if __name__ == "__main__":
    SidebarApp().run()
