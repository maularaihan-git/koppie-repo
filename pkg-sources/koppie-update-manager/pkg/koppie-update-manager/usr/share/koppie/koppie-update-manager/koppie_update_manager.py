#!/usr/bin/env python3
"""
Koppie Update Manager (KUM)
Pusat Pembaruan Sistem Koppie Linux dengan Dukungan Stable-Rolling Release (Delay 7 Hari)
"""

import os
import sys
import subprocess
import threading
import datetime
from pathlib import Path

# Pastikan lib lokal terdeteksi
CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if LIB_DIR.exists():
    sys.path.insert(0, str(LIB_DIR))

import customtkinter as ctk
from tkinter import messagebox

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Warna tema khas Koppie / Orchis
BG_DARK = "#1f1d20"
CARD_BG = "#2a2628"
CARD_HOVER = "#353032"
ACCENT_COLOR = "#b85d56"
ACCENT_HOVER = "#cf6e66"
TEXT_MAIN = "#f5f5f5"
TEXT_MUTED = "#b0a8a8"
SUCCESS_COLOR = "#4ea873"
WARNING_COLOR = "#e09f3e"
INFO_COLOR = "#5a9bd4"


class UpdateEngine:
    @staticmethod
    def get_snapshot_date(days_back=7):
        """Menghitung tanggal snapshot ALA (Arch Linux Archive) X hari yang lalu."""
        dt = datetime.datetime.now() - datetime.timedelta(days=days_back)
        return dt.strftime("%Y/%m/%d")

    @classmethod
    def configure_mirror_mode(cls, mode="stable"):
        """
        mode: 'stable' (delay 7 hari via ALA) atau 'bleeding' (server arch normal)
        """
        mirror_file = Path("/etc/pacman.d/mirrorlist")
        if not mirror_file.exists():
            return False, "File /etc/pacman.d/mirrorlist tidak ditemukan."

        if mode == "stable":
            date_str = cls.get_snapshot_date(7)
            ala_url = f"Server = https://archive.archlinux.org/repos/{date_str}/$repo/os/$arch\n"
            content = f"## Koppie Linux Stable Rolling Snapshot ({date_str})\n{ala_url}"
            # Cadangkan mirror lama jika belum dicadangkan
            backup_file = Path("/etc/pacman.d/mirrorlist.koppie-backup")
            if not backup_file.exists():
                try:
                    backup_file.write_text(mirror_file.read_text())
                except Exception:
                    pass
            try:
                cmd = ["pkexec", "tee", str(mirror_file)]
                proc = subprocess.run(cmd, input=content, text=True, capture_output=True)
                return proc.returncode == 0, f"Mirror diubah ke Stable Snapshot ({date_str})"
            except Exception as e:
                return False, str(e)
        else:
            # Kembalikan ke mirrorlist backup jika ada
            backup_file = Path("/etc/pacman.d/mirrorlist.koppie-backup")
            if backup_file.exists():
                try:
                    cmd = ["pkexec", "cp", str(backup_file), str(mirror_file)]
                    proc = subprocess.run(cmd, capture_output=True)
                    return proc.returncode == 0, "Mirror dikembalikan ke Normal (Bleeding Edge Arch)"
                except Exception as e:
                    return False, str(e)
            return True, "Mode Terkini (Bleeding Edge) aktif."

    @classmethod
    def check_updates(cls):
        """Memeriksa daftar paket yang bisa diperbarui."""
        updates = []
        # Coba gunakan checkupdates terlebih dahulu jika terpasang
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
            # Fallback: gunakan pacman -Qu
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


class KoppieUpdateManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Koppie Update Manager (KUM)")
        self.geometry("820x700")
        self.minsize(750, 600)
        self.configure(fg_color=BG_DARK)

        self.engine = UpdateEngine()
        self.updates_list = []
        self.is_updating = False

        self.build_ui()
        self.check_updates_async()

    def build_ui(self):
        # HEADER BAR
        header_frame = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12)
        header_frame.pack(fill="x", padx=20, pady=(18, 12))

        logo_badge = ctk.CTkLabel(
            header_frame,
            text=" K ",
            font=("Ubuntu", 22, "bold"),
            fg_color=ACCENT_COLOR,
            text_color="#ffffff",
            corner_radius=8,
            width=42,
            height=42
        )
        logo_badge.pack(side="left", padx=(16, 12), pady=14)

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", fill="y", pady=10)

        title_lbl = ctk.CTkLabel(
            title_box,
            text="Koppie Update Manager",
            font=("Ubuntu", 18, "bold"),
            text_color=TEXT_MAIN
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            title_box,
            text="Pusat Pembaruan Sistem Koppie Linux (Stable-Rolling Edition)",
            font=("Ubuntu", 12),
            text_color=TEXT_MUTED
        )
        subtitle_lbl.pack(anchor="w")

        self.check_btn = ctk.CTkButton(
            header_frame,
            text="🔄 Periksa Update",
            font=("Ubuntu", 13, "bold"),
            fg_color=CARD_HOVER,
            hover_color=ACCENT_COLOR,
            text_color=TEXT_MAIN,
            width=130,
            height=36,
            corner_radius=8,
            command=self.check_updates_async
        )
        self.check_btn.pack(side="right", padx=16)

        # STABLE ROLLING MODE SELECTOR CARD
        mode_card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12)
        mode_card.pack(fill="x", padx=20, pady=(0, 12))

        mode_header = ctk.CTkLabel(
            mode_card,
            text="🛡️ Mode Stabilitas Pembaruan (Rolling Release)",
            font=("Ubuntu", 13, "bold"),
            text_color=TEXT_MAIN
        )
        mode_header.pack(anchor="w", padx=16, pady=(10, 4))

        self.mode_var = ctk.StringVar(value="stable")
        mode_radio_frame = ctk.CTkFrame(mode_card, fg_color="transparent")
        mode_radio_frame.pack(fill="x", padx=16, pady=(0, 10))

        radio_stable = ctk.CTkRadioButton(
            mode_radio_frame,
            text="Mode Stabil Koppie (Tahan Pembaruan 7 Hari via Snapshot Arch)",
            variable=self.mode_var,
            value="stable",
            font=("Ubuntu", 12),
            text_color=TEXT_MAIN,
            fg_color=ACCENT_COLOR,
            command=self.on_mode_change
        )
        radio_stable.pack(side="left", padx=(0, 20))

        radio_bleeding = ctk.CTkRadioButton(
            mode_radio_frame,
            text="Mode Terkini (Langsung dari Arch Utama)",
            variable=self.mode_var,
            value="bleeding",
            font=("Ubuntu", 12),
            text_color=TEXT_MUTED,
            fg_color=ACCENT_COLOR,
            command=self.on_mode_change
        )
        radio_bleeding.pack(side="left")

        # STATUS CARD
        self.status_card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12)
        self.status_card.pack(fill="x", padx=20, pady=(0, 12))

        self.status_icon_lbl = ctk.CTkLabel(
            self.status_card,
            text="⏳ Memeriksa status sistem...",
            font=("Ubuntu", 14, "bold"),
            text_color=TEXT_MAIN
        )
        self.status_icon_lbl.pack(anchor="w", padx=16, pady=(12, 6))

        self.status_desc_lbl = ctk.CTkLabel(
            self.status_card,
            text="Sedang menyinkronkan daftar paket dengan repositori...",
            font=("Ubuntu", 12),
            text_color=TEXT_MUTED
        )
        self.status_desc_lbl.pack(anchor="w", padx=16, pady=(0, 12))

        # ACTION AREA: TOMBOL PERBARUI SEKARANG
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.pack(fill="x", padx=20, pady=(0, 8))

        self.update_now_btn = ctk.CTkButton(
            self.action_frame,
            text="🚀 Perbarui Sistem Sekarang",
            font=("Ubuntu", 14, "bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            height=40,
            corner_radius=8,
            state="disabled",
            command=self.start_system_update
        )
        self.update_now_btn.pack(side="left", padx=(0, 10))

        self.timer_chk_var = ctk.BooleanVar(value=True)
        self.timer_chk = ctk.CTkCheckBox(
            self.action_frame,
            text="Ingatkan notifikasi setiap minggu",
            variable=self.timer_chk_var,
            font=("Ubuntu", 12),
            text_color=TEXT_MUTED,
            fg_color=ACCENT_COLOR
        )
        self.timer_chk.pack(side="left", padx=10)

        # SCROLLABLE LIST OF PACKAGES
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            label_text="Daftar Paket yang Memerlukan Pembaruan",
            label_font=("Ubuntu", 13, "bold"),
            label_text_color=TEXT_MAIN
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        # LOG BOX
        self.log_box = ctk.CTkTextbox(
            self,
            height=90,
            fg_color="#181618",
            text_color="#a8d5ba",
            font=("Monospace", 11),
            corner_radius=8
        )
        self.log_box.pack(fill="x", padx=20, pady=(0, 16))
        self.log_box.insert("end", "Koppie Update Manager siap digunakan.\n")
        self.log_box.configure(state="disabled")

    def log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{text}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def on_mode_change(self):
        mode = self.mode_var.get()
        if mode == "stable":
            date_str = self.engine.get_snapshot_date(7)
            self.log(f"Mengalihkan ke Mode Stabil: Menahan paket rilis 7 hari (Snapshot: {date_str}).")
        else:
            self.log("Mengalihkan ke Mode Terkini: Menggunakan paket rilis langsung dari upstream Arch.")
        self.check_updates_async()

    def check_updates_async(self):
        if self.is_updating:
            return
        self.check_btn.configure(state="disabled", text="Memeriksa...")
        self.status_icon_lbl.configure(text="⏳ Sedang memeriksa pembaruan...")
        self.status_desc_lbl.configure(text="Menghubungkan ke repositori...")
        self.update_now_btn.configure(state="disabled")

        for w in self.scroll_frame.winfo_children():
            w.destroy()

        threading.Thread(target=self._check_thread, daemon=True).start()

    def _check_thread(self):
        # Refresh database pacman terlebih dahulu di background
        mode = self.mode_var.get()
        self.log("Menyinkronkan database paket...")
        subprocess.run(["pkexec", "pacman", "-Sy"], capture_output=True)

        updates = self.engine.check_updates()
        self.after(0, lambda: self._update_ui_with_results(updates))

    def _update_ui_with_results(self, updates):
        self.updates_list = updates
        self.check_btn.configure(state="normal", text="🔄 Periksa Update")

        if not updates:
            self.status_icon_lbl.configure(text="✔ Sistem Anda Sudah Paling Mutakhir!")
            self.status_desc_lbl.configure(text="Tidak ada pembaruan paket yang tertunda saat ini.")
            self.update_now_btn.configure(state="disabled")

            lbl = ctk.CTkLabel(
                self.scroll_frame,
                text="Semua paket berada pada versi terbaru untuk mode ini.",
                font=("Ubuntu", 13),
                text_color=TEXT_MUTED
            )
            lbl.pack(pady=30)
            self.log("Pemeriksaan selesai: Sistem up-to-date.")
        else:
            count = len(updates)
            self.status_icon_lbl.configure(text=f"📦 {count} Pembaruan Tersedia untuk Sistem Anda")
            self.status_desc_lbl.configure(text="Klik tombol di bawah untuk memulai proses pembaruan aman.")
            self.update_now_btn.configure(state="normal")

            for item in updates:
                row = ctk.CTkFrame(self.scroll_frame, fg_color=CARD_BG, corner_radius=8)
                row.pack(fill="x", pady=4, padx=4)

                pkg_lbl = ctk.CTkLabel(
                    row,
                    text=f" {item['name']} ",
                    font=("Ubuntu", 13, "bold"),
                    text_color=TEXT_MAIN
                )
                pkg_lbl.pack(side="left", padx=12, pady=8)

                ver_lbl = ctk.CTkLabel(
                    row,
                    text=f"{item['old']}  ➔  {item['new']}",
                    font=("Ubuntu", 12),
                    text_color=SUCCESS_COLOR
                )
                ver_lbl.pack(side="right", padx=12, pady=8)

            self.log(f"Pemeriksaan selesai: Ditemukan {count} paket yang dapat diperbarui.")

    def start_system_update(self):
        if self.is_updating or not self.updates_list:
            return

        confirm = messagebox.askyesno(
            "Konfirmasi Pembaruan",
            f"Apakah Anda yakin ingin memperbarui {len(self.updates_list)} paket sistem Koppie Linux?"
        )
        if not confirm:
            return

        self.is_updating = True
        self.update_now_btn.configure(state="disabled", text="Sedang Memperbarui...")
        self.check_btn.configure(state="disabled")
        self.log("Memulai proses pembaruan sistem via pacman -Syu...")

        def _update_thread():
            cmd = ["pkexec", "pacman", "-Syu", "--noconfirm"]
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                for line in proc.stdout:
                    l = line.strip()
                    if l:
                        self.after(0, lambda msg=l: self.log(msg))

                proc.wait()
                self.after(0, lambda: self._finish_update(proc.returncode))
            except Exception as e:
                self.after(0, lambda: self.log(f"❌ Error: {str(e)}"))
                self.after(0, lambda: self._finish_update(1))

        threading.Thread(target=_update_thread, daemon=True).start()

    def _finish_update(self, code):
        self.is_updating = False
        self.update_now_btn.configure(state="normal", text="🚀 Perbarui Sistem Sekarang")
        self.check_btn.configure(state="normal")
        if code == 0:
            self.log("✔ Pembaruan sistem selesai dengan sukses!")
            messagebox.showinfo(
                "Pembaruan Selesai",
                "Sistem Koppie Linux Anda telah berhasil diperbarui ke versi terbaru!"
            )
            self.check_updates_async()
        else:
            self.log(f"❌ Proses pembaruan dibatalkan atau terjadi kesalahan (Kode: {code}).")


def check_polkit_auth():
    try:
        res = subprocess.run(["pkexec", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            print("Autentikasi dibatalkan oleh pengguna.")
            sys.exit(0)
    except Exception as e:
        print(f"Peringatan polkit: {e}")


if __name__ == "__main__":
    check_polkit_auth()
    app = KoppieUpdateManagerApp()
    app.mainloop()
