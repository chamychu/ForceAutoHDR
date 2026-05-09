from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys
from tkinter import filedialog, messagebox

import customtkinter

from .registry import (
    InvalidExecutableError,
    RegistryEntryNotManagedError,
    RegistryUnavailableError,
    delete_autohdr_entry,
    list_autohdr_entries,
    write_autohdr_entry,
)


APP_TITLE = "ForceAutoHDR v1.0.0.4"
NO_GAMES_FOUND = "No Games Found"


class ForceAutoHDRApp:
    def __init__(self):
        configure_dpi_awareness()
        customtkinter.set_appearance_mode("light")
        customtkinter.set_default_color_theme("dark-blue")

        self.app = customtkinter.CTk()
        self.app.geometry("400x240")
        self.app.title(APP_TITLE)
        set_window_icon(self.app)

        self.keys_drop = customtkinter.CTkOptionMenu(
            master=self.app,
            values=[NO_GAMES_FOUND],
        )
        self.keys_drop.place(relx=0.5, rely=0.2, anchor=customtkinter.CENTER)

        add_button = customtkinter.CTkButton(
            master=self.app,
            text="Add Game EXE",
            command=self.add_game,
        )
        add_button.place(relx=0.5, rely=0.65, anchor=customtkinter.CENTER)

        delete_button = customtkinter.CTkButton(
            master=self.app,
            text="Delete Game EXE",
            command=self.delete_game,
        )
        delete_button.place(relx=0.5, rely=0.80, anchor=customtkinter.CENTER)

        self.refresh_games()

    def add_game(self):
        exe_path = filedialog.askopenfilename(
            title="Select EXE",
            filetypes=[("Executable files", "*.exe")],
        )
        if not exe_path:
            return

        try:
            entry = write_autohdr_entry(exe_path)
        except (InvalidExecutableError, RegistryUnavailableError, OSError) as exc:
            messagebox.showerror(title="Error", message=str(exc))
            return

        messagebox.showinfo(
            title="Done.",
            message=f"Added '{entry.exe_name}' to the AutoHDR registry list.",
        )
        self.refresh_games(selected=entry.key_name)

    def delete_game(self):
        key_name = self.keys_drop.get()
        if key_name == NO_GAMES_FOUND:
            messagebox.showerror(title="Error", message="No forced AutoHDR entries found.")
            return

        confirmed = messagebox.askyesno(
            title="Warning.",
            message=f"Delete forced AutoHDR registry entry '{key_name}'?",
        )
        if not confirmed:
            return

        try:
            delete_autohdr_entry(key_name)
        except (RegistryEntryNotManagedError, RegistryUnavailableError, OSError) as exc:
            messagebox.showerror(title="Error", message=str(exc))
            return

        messagebox.showinfo(
            title="Done.",
            message=f"Deleted forced AutoHDR registry entry '{key_name}'.",
        )
        self.refresh_games()

    def refresh_games(self, selected=None):
        try:
            entries = list_autohdr_entries()
        except (RegistryUnavailableError, OSError) as exc:
            entries = []
            messagebox.showerror(title="Error", message=str(exc))

        values = entries or [NO_GAMES_FOUND]
        self.keys_drop.configure(values=values)

        if selected in values:
            self.keys_drop.set(selected)
        else:
            self.keys_drop.set(values[0])

    def run(self):
        self.app.mainloop()


def configure_dpi_awareness():
    if os.name != "nt":
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware(True)
        except (AttributeError, OSError):
            return


def set_window_icon(window):
    icon_path = resource_path("Resources/hdr.ico")
    if not icon_path.exists():
        return

    try:
        window.iconbitmap(str(icon_path))
    except OSError:
        return


def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base_path / relative_path


def main():
    ForceAutoHDRApp().run()

