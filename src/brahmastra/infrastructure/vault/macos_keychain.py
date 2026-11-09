"""
macOS Keychain vault implementation using native /usr/bin/security tool.
"""

import subprocess
from typing import Optional
from brahmastra.domain.vault.interface import VaultInterface


class MacOSKeychainVault(VaultInterface):
    """
    Manages secrets using the native macOS Keychain via the 'security' CLI.
    Runs natively on Apple Silicon (arm64) and Intel (x86_64).
    """

    def __init__(self, executable_path: str = "/usr/bin/security"):
        self.executable_path = executable_path

    def store_secret(self, service: str, account: str, secret: str) -> str:
        """
        Store or update a secret in macOS Keychain.
        '-U' flag ensures existing items are updated in place.
        """
        if not secret:
            raise ValueError("Secret cannot be empty.")

        cmd = [
            self.executable_path,
            "add-generic-password",
            "-a", account,
            "-s", service,
            "-w", secret,
            "-U",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            err_msg = res.stderr.strip() or f"Process exited with code {res.returncode}"
            raise RuntimeError(f"Failed to store secret in macOS Keychain: {err_msg}")

        return f"vault:{service}:{account}"

    def get_secret(self, service: str, account: str) -> Optional[str]:
        """
        Retrieve secret plaintext from macOS Keychain.
        '-w' flag prints only the password itself.
        """
        cmd = [
            self.executable_path,
            "find-generic-password",
            "-a", account,
            "-s", service,
            "-w",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            # Output ends with a newline, strip only trailing newline
            return res.stdout.rstrip("\r\n")
        return None

    def delete_secret(self, service: str, account: str) -> bool:
        """
        Delete a secret from macOS Keychain.
        """
        cmd = [
            self.executable_path,
            "delete-generic-password",
            "-a", account,
            "-s", service,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0

    def has_secret(self, service: str, account: str) -> bool:
        """
        Check if secret exists in macOS Keychain without printing its secret content.
        """
        cmd = [
            self.executable_path,
            "find-generic-password",
            "-a", account,
            "-s", service,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0
