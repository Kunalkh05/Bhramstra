"""
System diagnostics and environment check ('doctor' command).
"""

import os
import platform
import shutil
import sqlite3
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

from brahmastra.infrastructure.config import get_storage_dir

console = Console()


def run_doctor() -> bool:
    """
    Perform pre-flight system diagnostics.
    Returns True if all critical checks pass, False otherwise.
    """
    console.print("\n[bold cyan]BRAHMASTRA System Health Check[/bold cyan]")
    console.print("[dim]Evaluating environment, OS, architecture, and system capabilities...[/dim]\n")

    table = Table(title="Diagnostic Results", show_lines=True)
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Component", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    all_passed = True

    # 1. Python Version Check
    py_ver = sys.version_info
    py_ver_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver >= (3, 10):
        table.add_row("Runtime", "Python Version", "[green]PASS[/green]", f"Python {py_ver_str} (>= 3.10 required)")
    else:
        all_passed = False
        table.add_row("Runtime", "Python Version", "[red]FAIL[/red]", f"Python {py_ver_str} (Python 3.10+ required)")

    # 2. Operating System Check (macOS / Darwin focus)
    os_name = platform.system()
    os_release = platform.release()
    if os_name == "Darwin":
        table.add_row("Platform", "Operating System", "[green]PASS[/green]", f"macOS (Darwin {os_release})")
    elif os_name == "Linux":
        table.add_row("Platform", "Operating System", "[green]PASS[/green]", f"Linux ({os_release})")
    else:
        table.add_row("Platform", "Operating System", "[yellow]WARN[/yellow]", f"{os_name} (Darwin/Linux recommended)")

    # 3. CPU Architecture Check (Apple Silicon ARM64 vs Intel x86_64)
    arch = platform.machine().lower()
    if arch in ("arm64", "aarch64"):
        table.add_row("Hardware", "CPU Architecture", "[green]PASS[/green]", f"Apple Silicon / ARM64 ({arch})")
    elif arch in ("x86_64", "amd64"):
        table.add_row("Hardware", "CPU Architecture", "[green]PASS[/green]", f"Intel / x86_64 ({arch})")
    else:
        table.add_row("Hardware", "CPU Architecture", "[yellow]WARN[/yellow]", f"Architecture: {arch}")

    # 4. Standard SQLite Library Check
    try:
        conn = sqlite3.connect(":memory:")
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.fetchone()
        conn.close()
        table.add_row("Database", "SQLite Engine", "[green]PASS[/green]", f"SQLite {sqlite3.sqlite_version} ready")
    except Exception as exc:
        all_passed = False
        table.add_row("Database", "SQLite Engine", "[red]FAIL[/red]", f"Error initializing SQLite: {exc}")

    # 5. OS Vault / Keychain Tool Check (for macOS security tool)
    if os_name == "Darwin":
        security_path = shutil.which("security")
        if security_path:
            table.add_row("Vault", "macOS Keychain CLI", "[green]PASS[/green]", f"Found at {security_path}")
        else:
            table.add_row("Vault", "macOS Keychain CLI", "[yellow]WARN[/yellow]", "'security' CLI tool not in PATH")
    else:
        table.add_row("Vault", "OS Vault", "[green]PASS[/green]", "Non-Darwin fallback vault supported")

    # 6. Workspace & Configuration Storage Permissions
    config_dir = get_storage_dir()
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        test_file = config_dir / ".doctor_probe"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        table.add_row("Storage", "Config Directory", "[green]PASS[/green]", f"Writable ({config_dir})")
    except Exception as exc:
        all_passed = False
        table.add_row("Storage", "Config Directory", "[red]FAIL[/red]", f"Cannot write to {config_dir}: {exc}")

    console.print(table)

    if all_passed:
        console.print("\n[bold green]✓ System is healthy and ready for BRAHMASTRA AI.[/bold green]\n")
    else:
        console.print("\n[bold red]✗ Some checks failed. Please review the details above.[/bold red]\n")

    return all_passed
