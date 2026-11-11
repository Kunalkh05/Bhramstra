"""
Windows Credential Manager vault implementation using native Advapi32.dll C APIs.
Eliminates command-line argument exposure in process table (argv).
"""

import sys
import ctypes
from typing import Optional, Dict, Tuple
from brahmastra.domain.vault.interface import VaultInterface

# Win32 Constants
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168


class WindowsCredentialVault(VaultInterface):
    """
    Manages secrets using Windows Credential Manager.
    Uses native C bindings to Advapi32.dll to guarantee zero secret exposure
    in process argument vectors (argv) on Windows.
    Includes a process-scoped in-memory cache to reduce latency.
    """

    def __init__(self, use_native: Optional[bool] = None):
        if use_native is None:
            self.use_native = sys.platform == "win32"
        else:
            self.use_native = use_native

        self._advapi = None
        self._cache: Dict[Tuple[str, str], str] = {}

        if self.use_native:
            self._init_native_bindings()

    def _init_native_bindings(self):
        try:
            self._advapi = ctypes.windll.Advapi32
        except Exception:
            self.use_native = False

    def _format_target(self, service: str, account: str) -> str:
        return f"brahmastra:{service}:{account}"

    def store_secret(self, service: str, account: str, secret: str) -> str:
        """
        Store or update a secret in Windows Credential Manager.
        Fails closed if native Windows bindings are unavailable.
        """
        if not secret:
            raise ValueError("Secret cannot be empty.")

        if not self.use_native or not self._advapi:
            raise RuntimeError(
                "Native Windows Credential Manager (Advapi32) is required to store credentials securely. "
                "Fail-closed policy prevents insecure storage."
            )

        target = self._format_target(service, account)
        secret_bytes = secret.encode("utf-8")

        # Define structure dynamically
        class CREDENTIALW(ctypes.Structure):
            _fields_ = [
                ("Flags", ctypes.c_uint32),
                ("Type", ctypes.c_uint32),
                ("TargetName", ctypes.c_wchar_p),
                ("Comment", ctypes.c_wchar_p),
                ("LastWritten", ctypes.c_uint64),
                ("CredentialBlobSize", ctypes.c_uint32),
                ("CredentialBlob", ctypes.c_char_p),
                ("Persist", ctypes.c_uint32),
                ("AttributeCount", ctypes.c_uint32),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", ctypes.c_wchar_p),
                ("UserName", ctypes.c_wchar_p),
            ]

        cred = CREDENTIALW()
        cred.Flags = 0
        cred.Type = CRED_TYPE_GENERIC
        cred.TargetName = target
        cred.Comment = "BRAHMASTRA Provider Credential"
        cred.CredentialBlobSize = len(secret_bytes)
        cred.CredentialBlob = secret_bytes
        cred.Persist = CRED_PERSIST_LOCAL_MACHINE
        cred.AttributeCount = 0
        cred.Attributes = None
        cred.TargetAlias = None
        cred.UserName = account

        try:
            res = self._advapi.CredWriteW(ctypes.byref(cred), 0)
            if not res:
                err = getattr(ctypes, "GetLastError", lambda: -1)()
                raise RuntimeError(f"CredWriteW failed with Win32 error code {err}")
        except Exception as exc:
            if not isinstance(exc, RuntimeError):
                raise RuntimeError(f"Failed to write to Windows Credential Manager: {exc}") from exc
            raise

        self._cache[(service, account)] = secret
        return f"vault:{service}:{account}"

    def get_secret(self, service: str, account: str) -> Optional[str]:
        """Retrieve a secret from Windows Credential Manager."""
        if (service, account) in self._cache:
            return self._cache[(service, account)]

        if not self.use_native or not self._advapi:
            return None

        target = self._format_target(service, account)

        class CREDENTIALW(ctypes.Structure):
            _fields_ = [
                ("Flags", ctypes.c_uint32),
                ("Type", ctypes.c_uint32),
                ("TargetName", ctypes.c_wchar_p),
                ("Comment", ctypes.c_wchar_p),
                ("LastWritten", ctypes.c_uint64),
                ("CredentialBlobSize", ctypes.c_uint32),
                ("CredentialBlob", ctypes.c_char_p),
                ("Persist", ctypes.c_uint32),
                ("AttributeCount", ctypes.c_uint32),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", ctypes.c_wchar_p),
                ("UserName", ctypes.c_wchar_p),
            ]

        p_cred = ctypes.POINTER(CREDENTIALW)()
        try:
            res = self._advapi.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(p_cred))
            if not res:
                return None

            cred = p_cred.contents
            blob_size = cred.CredentialBlobSize
            raw_data = ctypes.string_at(cred.CredentialBlob, blob_size)
            secret = raw_data.decode("utf-8")

            if hasattr(self._advapi, "CredFree"):
                self._advapi.CredFree(p_cred)

            self._cache[(service, account)] = secret
            return secret
        except Exception:
            return None

    def delete_secret(self, service: str, account: str) -> bool:
        """Delete a secret from Windows Credential Manager."""
        self._cache.pop((service, account), None)

        if not self.use_native or not self._advapi:
            return False

        target = self._format_target(service, account)
        try:
            res = self._advapi.CredDeleteW(target, CRED_TYPE_GENERIC, 0)
            return bool(res)
        except Exception:
            return False

    def has_secret(self, service: str, account: str) -> bool:
        """Check if a secret exists in Windows Credential Manager."""
        return self.get_secret(service, account) is not None
