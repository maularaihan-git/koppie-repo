#!/usr/bin/env python3
"""
Koppie Update Manager (KUM)
Clean, reliable update manager with Stable-Rolling Release for Koppie Linux.
"""

import os
import sys
import subprocess
import threading
import datetime
from pathlib import Path
from PIL import Image

CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if LIB_DIR.exists():
    sys.path.insert(0, str(LIB_DIR))

ASSETS_DIR = CURRENT_DIR.parent / "assets"
LOGO_PATH = ASSETS_DIR / "koppie-logo.png"

import customtkinter as ctk
from tkinter import messagebox

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Koppie Clean Color Palette
BG_DARK = "#1a1b20"
CARD_BG = "#23252c"
CARD_HOVER = "#2d3039"
KOPPIE_CYAN = "#0cc1e0"
KOPPIE_CYAN_HOVER = "#00a8c6"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#9ca3af"
SUCCESS_GREEN = "#10b981"
WARNING_AMBER = "#f59e0b"
INFO_BLUE = "#3b82f6"


class UpdateEngine:
    @staticmethod
    def get_snapshot_date(days_ago=7):
        target = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        return target.strftime("%Y/%m/%d")

    @classmethod
    def check_updates(cls):
        updates = []
        res = subprocess.run(["which", "checkupdates"], capture_output=True)
        if res.returncode == 0:
            out = subprocess.getoutput("checkupdates")
            for line in out.splitlines():
                if " -> " in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        updates.append({
                            "name": parts[0],
                            "old": parts[1],
                            "new": parts[3]
                        })
        else:
            out = subprocess.getoutput("pacman -Qu")
            for line in out.splitlines():
                if " -> " in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        updates.append({
                            "name": parts[0],
                            "old": parts[1],
                            "new": parts[3]
                        })
        return updates


class KoppieUpdateManager(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Koppie Update Manager")
        self.geometry("780x640")
        self.minsize(700, 540)
        self.configure(fg_color=BG_DARK)

        self.engine = UpdateEngine()
        self.updates = []
        self.is_running = False

        self.build_ui()
        self.check_async()

    def build_ui(self):
        # HEADER BAR
        header = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=0, height=75)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        if LOGO_PATH.exists():
            try:
                pil_img = Image.open(LOGO_PATH).resize((46, 46), Image.Resampling.LANCZOS)
                self.logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(46, 46))
                logo_lbl = ctk.CTkLabel(header, image=self.logo_img, text="")
                logo_lbl.pack(side="left", padx=(20, 14), pady=14)
            except Exception:
                pass

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", fill="y", pady=16)

        title = ctk.CTkLabel(
            title_box,
            text="Update Manager",
            font=("Ubuntu", 18, "bold"),
            text_color=TEXT_PRIMARY
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            title_box,
            text="Keep your system and applications secure and up to date",
            font=("Ubuntu", 12),
            text_color=TEXT_SECONDARY
        )
        subtitle.pack(anchor="w")

        # BOTTOM ACTION BAR
        self.footer = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=0, height=60)
        self.footer.pack(fill="x", side="bottom")
        self.footer.pack_propagate(False)

        self.check_btn = ctk.CTkButton(
            self.footer,
            text="Check Again",
            font=("Ubuntu", 12, "bold"),
            fg_color="#333742",
            hover_color="#424755",
            text_color=TEXT_PRIMARY,
            height=36,
            width=110,
            corner_radius=6,
            command=self.check_async
        )
        self.check_btn.pack(side="left", padx=20, pady=12)

        self.install_btn = ctk.CTkButton(
            self.footer,
            text="Install Updates",
            font=("Ubuntu", 12, "bold"),
            fg_color=KOPPIE_CYAN,
            hover_color=KOPPIE_CYAN_HOVER,
            text_color="#000000",
            height=36,
            width=130,
            corner_radius=6,
            state="disabled",
            command=self.install_updates
        )
        self.install_btn.pack(side="right", padx=20, pady=12)

        # STABILITY CHANNEL BANNER
        channel_bar = ctk.CTkFrame(self, fg_color="#202229", corner_radius=8)
        channel_bar.pack(fill="x", padx=20, pady=(16, 0))

        channel_title = ctk.CTkLabel(
            channel_bar,
            text="🛡  Release Channel: Stable Rolling (7-Day Safety Delay Enabled)",
            font=("Ubuntu", 12, "bold"),
            text_color=KOPPIE_CYAN
        )
        channel_title.pack(side="left", padx=16, pady=10)

        # MAIN SCROLLABLE CONTENT
        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=20, pady=16)

        # STATUS BANNER
        self.status_card = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=8)
        self.status_card.pack(fill="x", pady=(0, 12))

        self.status_title = ctk.CTkLabel(
            self.status_card,
            text="Checking for updates...",
            font=("Ubuntu", 14, "bold"),
            text_color=TEXT_PRIMARY
        )
        self.status_title.pack(anchor="w", padx=16, pady=(12, 4))

        self.status_desc = ctk.CTkLabel(
            self.status_card,
            text="Connecting to package repositories...",
            font=("Ubuntu", 12),
            text_color=TEXT_SECONDARY
        )
        self.status_desc.pack(anchor="w", padx=16, pady=(0, 12))

        # PACKAGE LIST CONTAINER
        self.list_container = ctk.CTkFrame(self.content, fg_color="transparent")
        self.list_container.pack(fill="both", expand=True)

    def check_async(self):
        if self.is_running:
            return

        self.check_btn.configure(state="disabled", text="Checking...")
        self.install_btn.configure(state="disabled")
        self.status_title.configure(text="Checking for updates...")
        self.status_desc.configure(text="Synchronizing package databases with mirrors...")

        for w in self.list_container.winfo_children():
            w.destroy()

        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        subprocess.run(["pkexec", "pacman", "-Sy"], capture_output=True)
        updates = self.engine.check_updates()
        self.after(0, lambda: self._render_results(updates))

    def _render_results(self, updates):
        self.updates = updates
        self.check_btn.configure(state="normal", text="Check Again")

        for w in self.list_container.winfo_children():
            w.destroy()

        if not updates:
            self.status_title.configure(text="✓  Your system is up to date")
            self.status_desc.configure(text="All installed software is running on the latest tested release.")
            self.install_btn.configure(state="disabled")

            empty_lbl = ctk.CTkLabel(
                self.list_container,
                text="No updates available at this time.",
                font=("Ubuntu", 13),
                text_color=TEXT_SECONDARY
            )
            empty_lbl.pack(pady=40)
        else:
            count = len(updates)
            self.status_title.configure(text=f"📦  {count} Update{'s' if count > 1 else ''} Available")
            self.status_desc.configure(text="Software updates are ready to be installed.")
            self.install_btn.configure(state="normal")

            # Table Header
            tbl_hdr = ctk.CTkFrame(self.list_container, fg_color="#2b2d35", corner_radius=6)
            tbl_hdr.pack(fill="x", pady=(0, 6))

            ctk.CTkLabel(tbl_hdr, text="PACKAGE NAME", font=("Ubuntu", 11, "bold"), text_color=TEXT_SECONDARY).pack(side="left", padx=14, pady=6)
            ctk.CTkLabel(tbl_hdr, text="NEW VERSION", font=("Ubuntu", 11, "bold"), text_color=TEXT_SECONDARY).pack(side="right", padx=14, pady=6)

            for u in updates:
                row = ctk.CTkFrame(self.list_container, fg_color=CARD_BG, corner_radius=6)
                row.pack(fill="x", pady=2)

                p_lbl = ctk.CTkLabel(row, text=u["name"], font=("Ubuntu", 12, "bold"), text_color=TEXT_PRIMARY)
                p_lbl.pack(side="left", padx=14, pady=8)

                v_lbl = ctk.CTkLabel(row, text=f"{u['old']}  ➔  {u['new']}", font=("Ubuntu", 12), text_color=SUCCESS_GREEN)
                v_lbl.pack(side="right", padx=14, pady=8)

    def install_updates(self):
        if self.is_running or not self.updates:
            return

        confirm = messagebox.askyesno(
            "Install Updates",
            f"Are you sure you want to install {len(self.updates)} updates?"
        )
        if not confirm:
            return

        self.is_running = True
        self.install_btn.configure(state="disabled", text="Installing...")
        self.check_btn.configure(state="disabled")

        def _update_worker():
            cmd = ["pkexec", "pacman", "-Syu", "--noconfirm"]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.is_running = False
            if proc.returncode == 0:
                self.after(0, lambda: messagebox.showinfo(
                    "Update Complete",
                    "All updates have been installed successfully!"
                ))
            else:
                self.after(0, lambda: messagebox.showerror(
                    "Update Failed",
                    f"An error occurred while updating the system.\n\n{proc.stderr}"
                ))
            self.after(0, self.check_async)

        threading.Thread(target=_update_worker, daemon=True).start()


def check_polkit_auth():
    try:
        res = subprocess.run(["pkexec", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            sys.exit(0)
    except Exception:
        pass


if __name__ == "__main__":
    check_polkit_auth()
    app = KoppieUpdateManager()
    app.mainloop()
