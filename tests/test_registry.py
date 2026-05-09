import unittest

from force_autohdr.registry import (
    AUTOHDR_BEHAVIORS,
    DIRECT3D_PATH,
    InvalidExecutableError,
    RegistryEntryNotManagedError,
    entry_from_exe_path,
    delete_autohdr_entry,
    list_autohdr_entries,
    write_autohdr_entry,
)


class FakeKey:
    def __init__(self, registry, path):
        self.registry = registry
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeWinReg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 1
    KEY_SET_VALUE = 2
    KEY_WOW64_64KEY = 4
    REG_SZ = "REG_SZ"

    def __init__(self):
        self.keys = set()
        self.values = {}

    def CreateKey(self, root_or_key, path):
        return self.CreateKeyEx(root_or_key, path, 0, self.KEY_SET_VALUE)

    def CreateKeyEx(self, root_or_key, path, _reserved, _access):
        full_path = self._full_path(root_or_key, path)
        self._create_path(full_path)
        return FakeKey(self, full_path)

    def OpenKey(self, root_or_key, path, _reserved, _access):
        full_path = self._full_path(root_or_key, path)
        if full_path not in self.keys:
            raise FileNotFoundError(full_path)
        return FakeKey(self, full_path)

    def SetValueEx(self, key, name, _reserved, value_type, value):
        self.values[(key.path, name)] = (value, value_type)

    def QueryValueEx(self, key, name):
        try:
            return self.values[(key.path, name)]
        except KeyError as exc:
            raise FileNotFoundError(name) from exc

    def EnumKey(self, key, index):
        prefix = f"{key.path}\\"
        children = sorted(
            candidate[len(prefix) :].split("\\", 1)[0]
            for candidate in self.keys
            if candidate.startswith(prefix)
            and "\\" not in candidate[len(prefix) :]
        )
        try:
            return children[index]
        except IndexError as exc:
            raise OSError(index) from exc

    def DeleteKey(self, key, name):
        path = f"{key.path}\\{name}"
        if path not in self.keys:
            raise FileNotFoundError(path)
        self.keys.remove(path)
        self.values = {
            value_key: value
            for value_key, value in self.values.items()
            if value_key[0] != path
        }

    def CloseKey(self, _key):
        return None

    def _full_path(self, root_or_key, path):
        if isinstance(root_or_key, FakeKey):
            return f"{root_or_key.path}\\{path}"
        if root_or_key == self.HKEY_CURRENT_USER:
            return path
        raise ValueError(f"Unexpected registry root: {root_or_key!r}")

    def _create_path(self, path):
        parts = path.split("\\")
        for index in range(1, len(parts) + 1):
            self.keys.add("\\".join(parts[:index]))


class RegistryTests(unittest.TestCase):
    def test_entry_from_exe_path_handles_uppercase_extension(self):
        entry = entry_from_exe_path(r"C:\Games\ExampleGame.EXE")

        self.assertEqual(entry.key_name, "ExampleGame")
        self.assertEqual(entry.exe_name, "ExampleGame.EXE")
        self.assertEqual(entry.registry_path, fr"{DIRECT3D_PATH}\ExampleGame")

    def test_entry_from_exe_path_rejects_non_exe_paths(self):
        with self.assertRaises(InvalidExecutableError):
            entry_from_exe_path(r"C:\Games\readme.txt")

    def test_write_autohdr_entry_sets_expected_values(self):
        registry = FakeWinReg()

        entry = write_autohdr_entry(r"C:\Games\ExampleGame.exe", registry=registry)

        key_path = fr"{DIRECT3D_PATH}\ExampleGame"
        self.assertEqual(entry.key_name, "ExampleGame")
        self.assertEqual(
            registry.values[(key_path, "Name")],
            ("ExampleGame.exe", registry.REG_SZ),
        )
        self.assertEqual(
            registry.values[(key_path, "D3DBehaviors")],
            (AUTOHDR_BEHAVIORS, registry.REG_SZ),
        )

    def test_list_autohdr_entries_filters_unrelated_direct3d_keys(self):
        registry = FakeWinReg()
        write_autohdr_entry(r"C:\Games\Managed.exe", registry=registry)
        unrelated = registry.CreateKeyEx(
            registry.HKEY_CURRENT_USER,
            fr"{DIRECT3D_PATH}\GraphicsDriverCache",
            0,
            registry.KEY_SET_VALUE,
        )
        registry.SetValueEx(unrelated, "Name", 0, registry.REG_SZ, "not managed")

        self.assertEqual(list_autohdr_entries(registry=registry), ["Managed"])

    def test_delete_autohdr_entry_removes_managed_key_without_admin_check(self):
        registry = FakeWinReg()
        write_autohdr_entry(r"C:\Games\Managed.exe", registry=registry)

        delete_autohdr_entry("Managed", registry=registry)

        self.assertNotIn(fr"{DIRECT3D_PATH}\Managed", registry.keys)

    def test_delete_autohdr_entry_refuses_unmanaged_direct3d_key(self):
        registry = FakeWinReg()
        registry.CreateKeyEx(
            registry.HKEY_CURRENT_USER,
            fr"{DIRECT3D_PATH}\GraphicsDriverCache",
            0,
            registry.KEY_SET_VALUE,
        )

        with self.assertRaises(RegistryEntryNotManagedError):
            delete_autohdr_entry("GraphicsDriverCache", registry=registry)


if __name__ == "__main__":
    unittest.main()
