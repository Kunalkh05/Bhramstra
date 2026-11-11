"""
macOS Keychain vault implementation using native Security.framework C-level APIs (BRAH-SEC-002).
Runs natively on Apple Silicon (arm64) and Intel (x86_64).
Eliminates command-line argument exposure in process table (argv).
"""

import sys
import shutil
import ctypes
from ctypes import c_char_p, c_uint32, c_void_p, POINTER, byref
import subprocess
from typing import Optional
from brahmastra.domain.vault.interface import VaultInterface

# Error codes from macOS Security/SecBase.h
errSecSuccess = 0
errSecDuplicateItem = -25299
errSecItemNotFound = -25300
errSecAuthFailed = -25293


class MacOSKeychainVault(VaultInterface):
    """
    Manages secrets using macOS Keychain.
    By default on macOS, uses native C bindings to Security.framework to guarantee
    zero secret exposure in process argument vectors (argv).
    Includes a process-scoped in-memory cache to reduce latency.
    """

    def __init__(
        self,
        executable_path: str = "/usr/bin/security",
        use_native: Optional[bool] = None,
    ):
        self.executable_path = executable_path
        if use_native is None:
            self.use_native = sys.platform == "darwin"
        else:
            self.use_native = use_native

        self._sec = None
        if self.use_native:
            self._init_native_bindings()

        self._cache: dict[tuple[str, str], str] = {}

    def _init_native_bindings(self):
        try:
            self._sec = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Security.framework/Security")

            # SecKeychainAddGenericPassword
            self._SecKeychainAddGenericPassword = self._sec.SecKeychainAddGenericPassword
            self._SecKeychainAddGenericPassword.argtypes = [
                c_void_p, c_uint32, c_char_p, c_uint32, c_char_p, c_uint32, c_void_p, POINTER(c_void_p)
            ]
            self._SecKeychainAddGenericPassword.restype = ctypes.c_int32

            # SecKeychainFindGenericPassword
            self._SecKeychainFindGenericPassword = self._sec.SecKeychainFindGenericPassword
            self._SecKeychainFindGenericPassword.argtypes = [
                c_void_p, c_uint32, c_char_p, c_uint32, c_char_p, POINTER(c_uint32), POINTER(c_void_p), POINTER(c_void_p)
            ]
            self._SecKeychainFindGenericPassword.restype = ctypes.c_int32

            # SecKeychainItemModifyAttributesAndData
            self._SecKeychainItemModifyAttributesAndData = self._sec.SecKeychainItemModifyAttributesAndData
            self._SecKeychainItemModifyAttributesAndData.argtypes = [
                c_void_p, c_void_p, c_uint32, c_void_p
            ]
            self._SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32

            # SecKeychainItemDelete
            self._SecKeychainItemDelete = self._sec.SecKeychainItemDelete
            self._SecKeychainItemDelete.argtypes = [c_void_p]
            self._SecKeychainItemDelete.restype = ctypes.c_int32

            # SecKeychainItemFreeContent
            self._SecKeychainItemFreeContent = self._sec.SecKeychainItemFreeContent
            self._SecKeychainItemFreeContent.argtypes = [c_void_p, c_void_p]
            self._SecKeychainItemFreeContent.restype = ctypes.c_int32

            # CFRelease from CoreFoundation
            self._cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
            self._CFRelease = self._cf.CFRelease
            self._CFRelease.argtypes = [c_void_p]
            self._CFRelease.restype = None
        except Exception:
            self.use_native = False

    def store_secret(self, service: str, account: str, secret: str) -> str:
        """
        Store or update a secret in macOS Keychain.
        Uses native in-memory pointers to prevent argument vector leakage.
        Fails closed if native Security.framework bindings are unavailable (BRAH-SEC-002).
        """
        if not secret:
            raise ValueError("Secret cannot be empty.")

        if self.use_native and self._sec:
            service_bytes = service.encode("utf-8")
            account_bytes = account.encode("utf-8")
            secret_bytes = secret.encode("utf-8")

            item_ref = c_void_p()
            pwd_len = c_uint32()
            pwd_data = c_void_p()
            status = self._SecKeychainFindGenericPassword(
                None,
                len(service_bytes),
                service_bytes,
                len(account_bytes),
                account_bytes,
                byref(pwd_len),
                byref(pwd_data),
                byref(item_ref),
            )

            if status == errSecSuccess:
                if pwd_data:
                    self._SecKeychainItemFreeContent(None, pwd_data)
                mod_status = self._SecKeychainItemModifyAttributesAndData(
                    item_ref,
                    None,
                    len(secret_bytes),
                    secret_bytes,
                )
                if hasattr(self, "_CFRelease") and item_ref:
                    self._CFRelease(item_ref)
                if mod_status != errSecSuccess:
                    raise RuntimeError(f"Failed to update secret in macOS Keychain: OSStatus {mod_status}")
            else:
                add_item_ref = c_void_p()
                add_status = self._SecKeychainAddGenericPassword(
                    None,
                    len(service_bytes),
                    service_bytes,
                    len(account_bytes),
                    account_bytes,
                    len(secret_bytes),
                    secret_bytes,
                    byref(add_item_ref),
                )
                if hasattr(self, "_CFRelease") and add_item_ref:
                    self._CFRelease(add_item_ref)
                if add_status != errSecSuccess:
                    raise RuntimeError(f"Failed to store secret in macOS Keychain: OSStatus {add_status}")

            self._cache[(service, account)] = secret
            return f"vault:{service}:{account}"

        # Insecure subprocess fallback is disabled to prevent plaintext secrets in argv (BRAH-SEC-002)
        raise RuntimeError(
            "Native macOS Security.framework C-level bindings are unavailable. "
            "Insecure command-line argument fallback is disabled for security (BRAH-SEC-002)."
        )

    def get_secret(self, service: str, account: str) -> Optional[str]:
        """
        Retrieve secret plaintext from macOS Keychain.
        Checks process-scoped cache first; falls back to native Keychain.
        """
        cache_key = (service, account)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self.use_native and self._sec:
            service_bytes = service.encode("utf-8")
            account_bytes = account.encode("utf-8")
            pwd_len = c_uint32()
            pwd_data = c_void_p()
            item_ref = c_void_p()

            status = self._SecKeychainFindGenericPassword(
                None,
                len(service_bytes),
                service_bytes,
                len(account_bytes),
                account_bytes,
                byref(pwd_len),
                byref(pwd_data),
                byref(item_ref),
            )
            if status == errSecSuccess:
                val = ctypes.string_at(pwd_data, pwd_len.value).decode("utf-8")
                self._SecKeychainItemFreeContent(None, pwd_data)
                if hasattr(self, "_CFRelease") and item_ref:
                    self._CFRelease(item_ref)
                self._cache[cache_key] = val
                return val
            if hasattr(self, "_CFRelease") and item_ref:
                self._CFRelease(item_ref)
            return None

        if not shutil.which(self.executable_path):
            return None

        cmd = [
            self.executable_path,
            "find-generic-password",
            "-a", account,
            "-s", service,
            "-w",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            secret = res.stdout.rstrip("\r\n")
            self._cache[cache_key] = secret
            return secret
        return None

    def delete_secret(self, service: str, account: str) -> bool:
        """
        Delete a secret from macOS Keychain and invalidate the cache.
        """
        self._cache.pop((service, account), None)

        if self.use_native and self._sec:
            service_bytes = service.encode("utf-8")
            account_bytes = account.encode("utf-8")
            pwd_len = c_uint32()
            pwd_data = c_void_p()
            item_ref = c_void_p()

            status = self._SecKeychainFindGenericPassword(
                None,
                len(service_bytes),
                service_bytes,
                len(account_bytes),
                account_bytes,
                byref(pwd_len),
                byref(pwd_data),
                byref(item_ref),
            )
            if status == errSecSuccess:
                if pwd_data:
                    self._SecKeychainItemFreeContent(None, pwd_data)
                del_status = self._SecKeychainItemDelete(item_ref)
                if hasattr(self, "_CFRelease") and item_ref:
                    self._CFRelease(item_ref)
                return del_status == errSecSuccess
            if hasattr(self, "_CFRelease") and item_ref:
                self._CFRelease(item_ref)
            return False

        if not shutil.which(self.executable_path):
            return False

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
        if (service, account) in self._cache:
            return True

        if self.use_native and self._sec:
            service_bytes = service.encode("utf-8")
            account_bytes = account.encode("utf-8")
            pwd_len = c_uint32()
            pwd_data = c_void_p()
            item_ref = c_void_p()

            status = self._SecKeychainFindGenericPassword(
                None,
                len(service_bytes),
                service_bytes,
                len(account_bytes),
                account_bytes,
                byref(pwd_len),
                byref(pwd_data),
                byref(item_ref),
            )
            if status == errSecSuccess:
                if pwd_data:
                    self._SecKeychainItemFreeContent(None, pwd_data)
                if hasattr(self, "_CFRelease") and item_ref:
                    self._CFRelease(item_ref)
                return True
            if hasattr(self, "_CFRelease") and item_ref:
                self._CFRelease(item_ref)
            return False

        if not shutil.which(self.executable_path):
            return False

        cmd = [
            self.executable_path,
            "find-generic-password",
            "-a", account,
            "-s", service,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0
