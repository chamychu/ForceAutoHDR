from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import ntpath

try:
    import winreg
except ImportError:  # pragma: no cover - exercised only on non-Windows hosts
    winreg = None


DIRECT3D_PATH = r"Software\Microsoft\Direct3D"
AUTOHDR_BEHAVIORS = "BufferUpgradeOverride=1;BufferUpgradeEnable10Bit=1"


class RegistryUnavailableError(RuntimeError):
    """Raised when Windows Registry APIs are unavailable."""


class InvalidExecutableError(ValueError):
    """Raised when a selected file is not a usable executable path."""


class RegistryEntryNotManagedError(ValueError):
    """Raised when a Direct3D key is not a forced AutoHDR entry."""


@dataclass(frozen=True)
class AutoHDREntry:
    exe_name: str
    key_name: str

    @property
    def registry_path(self) -> str:
        return fr"{DIRECT3D_PATH}\{self.key_name}"


def entry_from_exe_path(exe_path: str) -> AutoHDREntry:
    exe_name = ntpath.basename(str(exe_path))
    stem, extension = ntpath.splitext(exe_name)

    if not stem or extension.lower() != ".exe":
        raise InvalidExecutableError("Select a valid .exe file.")

    return AutoHDREntry(exe_name=exe_name, key_name=stem)


def write_autohdr_entry(exe_path: str, registry=None) -> AutoHDREntry:
    registry = _registry(registry)
    entry = entry_from_exe_path(exe_path)

    with _open_key(
        registry,
        registry.CreateKeyEx(
            registry.HKEY_CURRENT_USER,
            entry.registry_path,
            0,
            registry.KEY_SET_VALUE,
        ),
    ) as key:
        registry.SetValueEx(key, "Name", 0, registry.REG_SZ, entry.exe_name)
        registry.SetValueEx(
            key,
            "D3DBehaviors",
            0,
            registry.REG_SZ,
            AUTOHDR_BEHAVIORS,
        )

    return entry


def list_autohdr_entries(registry=None) -> list[str]:
    registry = _registry(registry)
    _ensure_direct3d_key(registry)

    with _open_key(
        registry,
        registry.OpenKey(
            registry.HKEY_CURRENT_USER,
            DIRECT3D_PATH,
            0,
            registry.KEY_READ | registry.KEY_WOW64_64KEY,
        ),
    ) as key:
        entries = []
        index = 0
        while True:
            try:
                key_name = registry.EnumKey(key, index)
            except OSError:
                break

            if _is_forced_autohdr_key(key_name, registry):
                entries.append(key_name)
            index += 1

    return entries


def delete_autohdr_entry(key_name: str, registry=None) -> None:
    registry = _registry(registry)

    if not key_name:
        raise RegistryEntryNotManagedError("Select a forced AutoHDR entry to delete.")

    if not _is_forced_autohdr_key(key_name, registry):
        raise RegistryEntryNotManagedError(
            f"'{key_name}' is not a forced AutoHDR registry entry."
        )

    with _open_key(
        registry,
        registry.OpenKey(
            registry.HKEY_CURRENT_USER,
            DIRECT3D_PATH,
            0,
            registry.KEY_SET_VALUE,
        ),
    ) as key:
        registry.DeleteKey(key, key_name)


def _registry(registry):
    if registry is not None:
        return registry

    if winreg is None:
        raise RegistryUnavailableError("ForceAutoHDR can only modify the registry on Windows.")

    return winreg


def _ensure_direct3d_key(registry) -> None:
    with _open_key(
        registry,
        registry.CreateKeyEx(
            registry.HKEY_CURRENT_USER,
            DIRECT3D_PATH,
            0,
            registry.KEY_SET_VALUE,
        ),
    ):
        return


def _is_forced_autohdr_key(key_name: str, registry) -> bool:
    try:
        with _open_key(
            registry,
            registry.OpenKey(
                registry.HKEY_CURRENT_USER,
                fr"{DIRECT3D_PATH}\{key_name}",
                0,
                registry.KEY_READ | registry.KEY_WOW64_64KEY,
            ),
        ) as key:
            behaviors, _value_type = registry.QueryValueEx(key, "D3DBehaviors")
    except (FileNotFoundError, OSError):
        return False

    return "BufferUpgradeOverride=1" in str(behaviors).split(";")


@contextmanager
def _open_key(registry, key):
    try:
        yield key
    finally:
        close_key = getattr(registry, "CloseKey", None)
        if close_key is not None:
            close_key(key)

