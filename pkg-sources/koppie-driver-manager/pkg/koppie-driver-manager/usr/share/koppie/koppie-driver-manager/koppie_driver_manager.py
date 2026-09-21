#!/usr/bin/env python3
"""
Koppie Driver Manager (KDM)
Aplikasi Deteksi Hardware & Manajemen Driver Otomatis untuk Koppie Linux
"""

import os
import sys
import subprocess
import threading
from pathlib import Path

# Pastikan lib lokal terdeteksi
CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if LIB_DIR.exists():
    sys.path.insert(0, str(LIB_DIR))

import customtkinter as ctk
from tkinter import messagebox

# Set tema CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Warna tema khas Koppie / Orchis (Warm Dark & Terracotta Accent)
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


class HardwareDetector:
    @staticmethod
    def get_dmi_info():
        vendor_file = Path("/sys/class/dmi/id/sys_vendor")
        product_file = Path("/sys/class/dmi/id/product_name")
        vendor = vendor_file.read_text().strip() if vendor_file.exists() else "Unknown Vendor"
        product = product_file.read_text().strip() if product_file.exists() else "Standard PC"
        return f"{vendor} {product}".strip()

    @staticmethod
    def get_cpu_info():
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[1].strip()
        except Exception:
            pass
        return "Unknown CPU"

    @staticmethod
    def get_kernel_info():
        return subprocess.getoutput("uname -r").strip()

    @staticmethod
    def is_package_installed(pkg_name):
        res = subprocess.run(["pacman", "-Q", pkg_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0

    @classmethod
    def scan_devices(cls):
        lspci_out = subprocess.getoutput("lspci -nnk")
        devices = []
        blocks = lspci_out.split("\n\n")

        # Cek kernel saat ini untuk menentukan tipe headers (misal linux-lts -> linux-lts-headers)
        kernel_ver = cls.get_kernel_info()
        headers_pkg = "linux-lts-headers" if "lts" in kernel_ver else "linux-headers"

        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue

            header = lines[0]
            driver_in_use = ""
            kernel_modules = ""
            subsystem = ""

            for line in lines[1:]:
                if line.startswith("Kernel driver in use:"):
                    driver_in_use = line.split(":", 1)[1].strip()
                elif line.startswith("Kernel modules:"):
                    kernel_modules = line.split(":", 1)[1].strip()
                elif line.startswith("Subsystem:"):
                    subsystem = line.split(":", 1)[1].strip()

            lower_hdr = header.lower()

            # 1. WIRELESS / WI-FI
            if "network controller" in lower_hdr or "wireless" in lower_hdr:
                dev = {
                    "type": "Wi-Fi (Wireless)",
                    "title": header.split(": ", 1)[-1] if ": " in header else header,
                    "subsystem": subsystem,
                    "driver": driver_in_use or "Tidak ada driver aktif",
                    "status": "info",
                    "recommendation": "",
                    "packages_to_install": [],
                }

                # Cek Broadcom (BCM43xx)
                if "broadcom" in lower_hdr or "14e4:" in lower_hdr:
                    if "4331" in lower_hdr or "4360" in lower_hdr or "43142" in lower_hdr or "4322" in lower_hdr:
                        is_wl_installed = cls.is_package_installed("broadcom-wl-dkms") or cls.is_package_installed("broadcom-wl")
                        is_headers_installed = cls.is_package_installed(headers_pkg)

                        if is_wl_installed and driver_in_use == "wl":
                            dev["status"] = "optimal"
                            dev["recommendation"] = "Driver Broadcom STA (wl) aktif dan berfungsi optimal."
                        else:
                            dev["status"] = "action_needed"
                            pkgs = []
                            if not is_headers_installed:
                                pkgs.append(headers_pkg)
                            if not is_wl_installed:
                                pkgs.append("broadcom-wl-dkms")
                            dev["packages_to_install"] = pkgs
                            dev["recommendation"] = f"Direkomendasikan: {', '.join(pkgs)} untuk mengaktifkan Wi-Fi Broadcom."
                    else:
                        dev["status"] = "optimal"
                        dev["recommendation"] = "Broadcom menggunakan modul bawaan kernel / b43."

                # Cek Intel Wireless
                elif "intel" in lower_hdr or "8086:" in lower_hdr:
                    dev["status"] = "optimal"
                    dev["recommendation"] = "Intel Wireless (iwlwifi) bawaan kernel Linux & linux-firmware."

                # Cek Realtek
                elif "realtek" in lower_hdr or "10ec:" in lower_hdr:
                    if driver_in_use:
                        dev["status"] = "optimal"
                        dev["recommendation"] = f"Driver Realtek ({driver_in_use}) aktif bawaan kernel."
                    else:
                        dev["status"] = "warning"
                        dev["recommendation"] = "Perangkat Realtek terdeteksi. Disarankan memastikan linux-firmware terpasang."

                # Lainnya (Atheros / MediaTek)
                else:
                    dev["status"] = "optimal"
                    dev["recommendation"] = f"Driver kernel: {driver_in_use or 'Bawaan kernel / linux-firmware'}"

                devices.append(dev)

            # 2. ETHERNET (LAN)
            elif "ethernet controller" in lower_hdr:
                devices.append({
                    "type": "Ethernet (LAN)",
                    "title": header.split(": ", 1)[-1] if ": " in header else header,
                    "subsystem": subsystem,
                    "driver": driver_in_use or "Tidak ada",
                    "status": "optimal",
                    "recommendation": f"Driver LAN aktif di kernel ({driver_in_use or 'generic'}).",
                    "packages_to_install": [],
                })

            # 3. GRAPHICS (GPU)
            elif any(k in lower_hdr for k in ["vga compatible", "3d controller", "display controller"]):
                dev = {
                    "type": "Kartu Grafis (GPU)",
                    "title": header.split(": ", 1)[-1] if ": " in header else header,
                    "subsystem": subsystem,
                    "driver": driver_in_use or "modesetting",
                    "status": "optimal",
                    "recommendation": "",
                    "packages_to_install": [],
                }

                if "nvidia" in lower_hdr or "10de:" in lower_hdr:
                    if driver_in_use == "nvidia":
                        dev["status"] = "optimal"
                        dev["recommendation"] = "Driver resmi NVIDIA Proprietary aktif."
                    else:
                        is_nv_installed = cls.is_package_installed("nvidia-open-dkms") or cls.is_package_installed("nvidia-dkms")
                        if not is_nv_installed:
                            dev["status"] = "action_needed"
                            dev["packages_to_install"] = [headers_pkg, "nvidia-open-dkms"]
                            dev["recommendation"] = f"Tersedia driver NVIDIA Proprietary ({headers_pkg}, nvidia-open-dkms)."
                        else:
                            dev["status"] = "optimal"
                            dev["recommendation"] = "Driver Nouveau open-source aktif."
                elif "intel" in lower_hdr or "8086:" in lower_hdr:
                    dev["status"] = "optimal"
                    dev["recommendation"] = f"Intel Graphics terakselerasi Mesa ({driver_in_use or 'i915'})."
                elif "advanced micro devices" in lower_hdr or "amd" in lower_hdr or "ati" in lower_hdr or "1002:" in lower_hdr:
                    dev["status"] = "optimal"
                    dev["recommendation"] = f"AMD Radeon terakselerasi Mesa ({driver_in_use or 'amdgpu'})."

                devices.append(dev)

        return devices


class KoppieDriverManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Koppie Driver Manager (KDM)")
        self.geometry("820x680")
        self.minsize(750, 580)
        self.configure(fg_color=BG_DARK)

        self.detector = HardwareDetector()
        self.devices = []

        self.build_ui()
        self.refresh_hardware_async()

    def build_ui(self):
        # HEADER BAR
        header_frame = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12)
        header_frame.pack(fill="x", padx=20, pady=(18, 12))

        # Icon Koppie (Badge 'K')
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
            text="Koppie Driver Manager",
            font=("Ubuntu", 18, "bold"),
            text_color=TEXT_MAIN
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            title_box,
            text="Deteksi otomatis & manajemen driver perangkat keras Koppie Linux",
            font=("Ubuntu", 12),
            text_color=TEXT_MUTED
        )
        subtitle_lbl.pack(anchor="w")

        # Tombol Refresh di kanan atas
        self.refresh_btn = ctk.CTkButton(
            header_frame,
            text="🔄 Pindai Ulang",
            font=("Ubuntu", 13, "bold"),
            fg_color=CARD_HOVER,
            hover_color=ACCENT_COLOR,
            text_color=TEXT_MAIN,
            width=120,
            height=36,
            corner_radius=8,
            command=self.refresh_hardware_async
        )
        self.refresh_btn.pack(side="right", padx=16)

        # INFO SISTEM CARD
        info_frame = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12)
        info_frame.pack(fill="x", padx=20, pady=(0, 12))

        dmi_text = self.detector.get_dmi_info()
        kernel_text = self.detector.get_kernel_info()
        cpu_text = self.detector.get_cpu_info()

        sys_lbl = ctk.CTkLabel(
            info_frame,
            text=f"💻 Perangkat: {dmi_text}   |   🐧 Kernel: {kernel_text}\n⚙️ CPU: {cpu_text}",
            font=("Ubuntu", 12),
            text_color=TEXT_MUTED,
            justify="left"
        )
        sys_lbl.pack(anchor="w", padx=16, pady=10)

        # DAFTAR HARDWARE (SCROLLABLE FRAME)
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            label_text="Perangkat & Driver Terdeteksi",
            label_font=("Ubuntu", 14, "bold"),
            label_text_color=TEXT_MAIN
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        # STATUS / LOG CONSOLE AREA
        self.log_box = ctk.CTkTextbox(
            self,
            height=80,
            fg_color="#181618",
            text_color="#a8d5ba",
            font=("Monospace", 11),
            corner_radius=8
        )
        self.log_box.pack(fill="x", padx=20, pady=(0, 16))
        self.log_box.insert("end", "Memulai pemindaian hardware...\n")
        self.log_box.configure(state="disabled")

    def log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{text}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def refresh_hardware_async(self):
        self.refresh_btn.configure(state="disabled", text="Memindai...")
        self.log("Memindai ulang perangkat hardware dengan lspci & kernel modules...")

        # Bersihkan list yang lama
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Jalankan di background thread agar UI tidak freeze
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        devices = self.detector.scan_devices()
        self.after(0, lambda: self._update_ui_with_devices(devices))

    def _update_ui_with_devices(self, devices):
        self.devices = devices
        self.refresh_btn.configure(state="normal", text="🔄 Pindai Ulang")

        if not devices:
            lbl = ctk.CTkLabel(
                self.scroll_frame,
                text="Tidak ada perangkat spesifik yang terdeteksi.",
                font=("Ubuntu", 13),
                text_color=TEXT_MUTED
            )
            lbl.pack(pady=20)
            return

        for dev in devices:
            self.create_device_card(dev)

        self.log(f"Pemindaian selesai: {len(devices)} pengontrol perangkat terdeteksi.")

    def create_device_card(self, dev):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=CARD_BG, corner_radius=10)
        card.pack(fill="x", pady=6, padx=4)

        # Bagian atas kartu: Jenis & Nama
        top_box = ctk.CTkFrame(card, fg_color="transparent")
        top_box.pack(fill="x", padx=14, pady=(10, 4))

        type_lbl = ctk.CTkLabel(
            top_box,
            text=f"[{dev['type']}]",
            font=("Ubuntu", 12, "bold"),
            text_color=ACCENT_COLOR
        )
        type_lbl.pack(side="left")

        # Badge status
        if dev["status"] == "optimal":
            badge_color = SUCCESS_COLOR
            badge_text = "✔ Optimal / Terpasang"
        elif dev["status"] == "action_needed":
            badge_color = WARNING_COLOR
            badge_text = "⚡ Perlu Install Driver"
        else:
            badge_color = INFO_COLOR
            badge_text = "ℹ Informasi"

        badge = ctk.CTkLabel(
            top_box,
            text=f" {badge_text} ",
            font=("Ubuntu", 11, "bold"),
            fg_color=badge_color,
            text_color="#ffffff",
            corner_radius=6
        )
        badge.pack(side="right")

        # Nama Hardware
        name_lbl = ctk.CTkLabel(
            card,
            text=dev["title"],
            font=("Ubuntu", 13, "bold"),
            text_color=TEXT_MAIN,
            anchor="w",
            justify="left"
        )
        name_lbl.pack(fill="x", padx=14, pady=(0, 4))

        # Driver & Rekomendasi
        driver_txt = f"Modul Kernel: {dev['driver']}"
        if dev.get("subsystem"):
            driver_txt += f"  |  Subsystem: {dev['subsystem']}"

        detail_lbl = ctk.CTkLabel(
            card,
            text=driver_txt,
            font=("Ubuntu", 11),
            text_color=TEXT_MUTED,
            anchor="w"
        )
        detail_lbl.pack(fill="x", padx=14, pady=(0, 4))

        rec_lbl = ctk.CTkLabel(
            card,
            text=dev["recommendation"],
            font=("Ubuntu", 12),
            text_color="#e6e1e1",
            anchor="w",
            justify="left"
        )
        rec_lbl.pack(fill="x", padx=14, pady=(0, 10))

        # Tombol Aksi jika butuh instalasi
        if dev["packages_to_install"]:
            btn_box = ctk.CTkFrame(card, fg_color="transparent")
            btn_box.pack(fill="x", padx=14, pady=(0, 10))

            pkgs_str = " ".join(dev["packages_to_install"])
            install_btn = ctk.CTkButton(
                btn_box,
                text=f"Pasang Driver ({pkgs_str})",
                font=("Ubuntu", 12, "bold"),
                fg_color=ACCENT_COLOR,
                hover_color=ACCENT_HOVER,
                height=32,
                corner_radius=6,
                command=lambda pkgs=dev["packages_to_install"]: self.install_driver(pkgs)
            )
            install_btn.pack(side="left")

    def install_driver(self, packages):
        pkgs_str = " ".join(packages)
        self.log(f"Memulai instalasi driver: {pkgs_str}...")

        def _run_install():
            # Menggunakan pkexec untuk meminta autentikasi root
            cmd = ["pkexec", "pacman", "-S", "--needed", "--noconfirm"] + packages
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                for line in proc.stdout:
                    clean_line = line.strip()
                    if clean_line:
                        self.after(0, lambda l=clean_line: self.log(l))

                proc.wait()
                if proc.returncode == 0:
                    self.after(0, lambda: self.log(f"✔ Berhasil memasang driver: {pkgs_str}!"))
                    self.after(0, self.refresh_hardware_async)
                    messagebox.showinfo(
                        "Instalasi Berhasil",
                        f"Driver {pkgs_str} berhasil dipasang!\nSilakan restart perangkat jika diperlukan."
                    )
                else:
                    self.after(0, lambda: self.log(f"❌ Instalasi gagal atau dibatalkan (Kode: {proc.returncode})."))
            except Exception as e:
                self.after(0, lambda: self.log(f"❌ Error: {str(e)}"))

        threading.Thread(target=_run_install, daemon=True).start()


def check_polkit_auth():
    # Jika bukan root, minta autentikasi polkit di awal sesuai permintaan sistem Koppie
    try:
        res = subprocess.run(["pkexec", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            print("Autentikasi dibatalkan oleh pengguna.")
            sys.exit(0)
    except Exception as e:
        print(f"Peringatan polkit: {e}")

if __name__ == "__main__":
    check_polkit_auth()
    app = KoppieDriverManagerApp()
    app.mainloop()
