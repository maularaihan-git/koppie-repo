#!/usr/bin/env python3
"""
Koppie Driver Manager (KDM)
Clean, user-friendly hardware driver utility for Koppie Linux.
"""

import os
import sys
import subprocess
import threading
from pathlib import Path
from PIL import Image

# Ensure bundled libraries are available
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


class HardwareScanner:
    @staticmethod
    def get_system_model():
        vendor_file = Path("/sys/class/dmi/id/sys_vendor")
        product_file = Path("/sys/class/dmi/id/product_name")
        vendor = vendor_file.read_text().strip() if vendor_file.exists() else "Unknown"
        product = product_file.read_text().strip() if product_file.exists() else "Computer"
        return f"{vendor} {product}".strip()

    @staticmethod
    def get_kernel_version():
        return subprocess.getoutput("uname -r").strip()

    @staticmethod
    def is_installed(pkg_name):
        res = subprocess.run(["pacman", "-Q", pkg_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0

    @classmethod
    def detect_devices(cls):
        lspci_out = subprocess.getoutput("lspci -nnk")
        devices = []
        blocks = lspci_out.split("\n\n")

        kernel_ver = cls.get_kernel_version()
        headers_pkg = "linux-lts-headers" if "lts" in kernel_ver else "linux-headers"

        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue

            header = lines[0]
            driver_in_use = ""
            subsystem = ""

            for line in lines[1:]:
                if line.startswith("Kernel driver in use:"):
                    driver_in_use = line.split(":", 1)[1].strip()
                elif line.startswith("Subsystem:"):
                    subsystem = line.split(":", 1)[1].strip()

            lower = header.lower()

            # 1. Wireless Network
            if "network controller" in lower or "wireless" in lower:
                dev = {
                    "category": "Wireless Network",
                    "name": header.split(": ", 1)[-1] if ": " in header else header,
                    "subsystem": subsystem,
                    "driver": driver_in_use or "None",
                    "type": "wifi",
                    "options": [],
                    "selected_option": 0,
                    "packages_needed": [],
                }

                if "broadcom" in lower or "14e4:" in lower:
                    if any(x in lower for x in ["4331", "4360", "43142", "4322", "43224", "43228"]):
                        is_wl = cls.is_installed("broadcom-wl-dkms") or cls.is_installed("broadcom-wl")
                        dev["options"] = [
                            {
                                "id": "wl",
                                "title": "broadcom-wl-dkms (Proprietary STA Driver)",
                                "desc": "Recommended for Broadcom Wi-Fi on MacBooks & laptops. Requires DKMS.",
                                "packages": [headers_pkg, "broadcom-wl-dkms"],
                                "installed": is_wl
                            },
                            {
                                "id": "none",
                                "title": "Do not use this driver (Open-source fallback)",
                                "desc": "Use kernel b43 or brcmsmac driver if supported.",
                                "packages": [],
                                "installed": not is_wl
                            }
                        ]
                        dev["selected_option"] = 0 if is_wl else 0
                        if not is_wl:
                            dev["packages_needed"] = [headers_pkg, "broadcom-wl-dkms"]
                    else:
                        dev["status_text"] = "Using open-source in-tree driver (b43/brcmfmac)"
                elif "intel" in lower or "8086:" in lower:
                    dev["status_text"] = "Using open-source Intel driver (iwlwifi) provided by the Linux kernel."
                elif "realtek" in lower or "10ec:" in lower:
                    dev["status_text"] = f"Using Realtek driver ({driver_in_use or 'rtw88'}) included in the kernel."
                else:
                    dev["status_text"] = f"Using kernel driver: {driver_in_use or 'Generic open-source driver'}"

                devices.append(dev)

            # 2. Graphics (GPU)
            elif any(k in lower for k in ["vga compatible", "3d controller", "display controller"]):
                dev = {
                    "category": "Graphics Adapter (GPU)",
                    "name": header.split(": ", 1)[-1] if ": " in header else header,
                    "subsystem": subsystem,
                    "driver": driver_in_use or "modesetting",
                    "type": "gpu",
                    "options": [],
                    "selected_option": 0,
                    "packages_needed": [],
                }

                if "nvidia" in lower or "10de:" in lower:
                    is_nv = cls.is_installed("nvidia-open-dkms") or cls.is_installed("nvidia-dkms")
                    dev["options"] = [
                        {
                            "id": "nvidia",
                            "title": "NVIDIA Proprietary Driver (DKMS)",
                            "desc": "Official high-performance driver with hardware acceleration & Vulkan.",
                            "packages": [headers_pkg, "nvidia-open-dkms"],
                            "installed": is_nv
                        },
                        {
                            "id": "nouveau",
                            "title": "Nouveau Open-Source Driver",
                            "desc": "Standard open-source driver included in the Linux kernel.",
                            "packages": [],
                            "installed": not is_nv
                        }
                    ]
                    dev["selected_option"] = 0 if is_nv else 1
                    if not is_nv:
                        dev["packages_needed"] = [headers_pkg, "nvidia-open-dkms"]
                elif "intel" in lower or "8086:" in lower:
                    dev["status_text"] = f"Using Intel Mesa driver ({driver_in_use or 'i915'}) with full 3D acceleration."
                elif "amd" in lower or "advanced micro devices" in lower or "1002:" in lower:
                    dev["status_text"] = f"Using AMD open-source driver ({driver_in_use or 'amdgpu'}) with Mesa."

                devices.append(dev)

        return devices


class KoppieDriverManager(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Koppie Driver Manager")
        self.geometry("780x620")
        self.minsize(700, 520)
        self.configure(fg_color=BG_DARK)

        self.devices = []
        self.option_vars = {}
        self.scanner = HardwareScanner()

        self.build_ui()
        self.scan_async()

    def build_ui(self):
        # HEADER BAR
        header = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=0, height=75)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Koppie Logo
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
            text="Driver Manager",
            font=("Ubuntu", 18, "bold"),
            text_color=TEXT_PRIMARY
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            title_box,
            text="Find and manage hardware drivers for your computer",
            font=("Ubuntu", 12),
            text_color=TEXT_SECONDARY
        )
        subtitle.pack(anchor="w")

        # BOTTOM ACTION BAR
        self.footer = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=0, height=60)
        self.footer.pack(fill="x", side="bottom")
        self.footer.pack_propagate(False)

        self.scan_btn = ctk.CTkButton(
            self.footer,
            text="Scan Again",
            font=("Ubuntu", 12, "bold"),
            fg_color="#333742",
            hover_color="#424755",
            text_color=TEXT_PRIMARY,
            height=36,
            width=110,
            corner_radius=6,
            command=self.scan_async
        )
        self.scan_btn.pack(side="left", padx=20, pady=12)

        self.apply_btn = ctk.CTkButton(
            self.footer,
            text="Apply Changes",
            font=("Ubuntu", 12, "bold"),
            fg_color=KOPPIE_CYAN,
            hover_color=KOPPIE_CYAN_HOVER,
            text_color="#000000",
            height=36,
            width=130,
            corner_radius=6,
            state="disabled",
            command=self.apply_changes
        )
        self.apply_btn.pack(side="right", padx=20, pady=12)

        # MAIN SCROLLABLE CONTENT
        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=20, pady=16)

        # System info badge
        self.info_lbl = ctk.CTkLabel(
            self.content,
            text="Detecting hardware configuration...",
            font=("Ubuntu", 12),
            text_color=TEXT_SECONDARY,
            anchor="w"
        )
        self.info_lbl.pack(fill="x", pady=(0, 12))

    def scan_async(self):
        self.scan_btn.configure(state="disabled", text="Scanning...")
        self.apply_btn.configure(state="disabled")

        for w in self.content.winfo_children():
            if w != self.info_lbl:
                w.destroy()

        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        devices = self.scanner.detect_devices()
        model = self.scanner.get_system_model()
        kernel = self.scanner.get_kernel_version()
        self.after(0, lambda: self._render_devices(devices, model, kernel))

    def _render_devices(self, devices, model, kernel):
        self.devices = devices
        self.scan_btn.configure(state="normal", text="Scan Again")
        self.info_lbl.configure(text=f"Computer: {model}  •  Kernel: {kernel}")

        has_actionable = False

        for idx, dev in enumerate(devices):
            card = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=8)
            card.pack(fill="x", pady=6)

            # Card Header
            header_box = ctk.CTkFrame(card, fg_color="transparent")
            header_box.pack(fill="x", padx=16, pady=(12, 6))

            cat_lbl = ctk.CTkLabel(
                header_box,
                text=dev["category"].upper(),
                font=("Ubuntu", 10, "bold"),
                text_color=KOPPIE_CYAN
            )
            cat_lbl.pack(anchor="w")

            dev_name = ctk.CTkLabel(
                card,
                text=dev["name"],
                font=("Ubuntu", 13, "bold"),
                text_color=TEXT_PRIMARY,
                anchor="w",
                justify="left"
            )
            dev_name.pack(fill="x", padx=16, pady=(0, 6))

            # Options or Status
            if dev.get("options"):
                var = ctk.IntVar(value=dev["selected_option"])
                self.option_vars[idx] = var

                opt_box = ctk.CTkFrame(card, fg_color="transparent")
                opt_box.pack(fill="x", padx=16, pady=(0, 12))

                for o_idx, opt in enumerate(dev["options"]):
                    r_btn = ctk.CTkRadioButton(
                        opt_box,
                        text=f"{opt['title']}\n{opt['desc']}",
                        variable=var,
                        value=o_idx,
                        font=("Ubuntu", 12),
                        text_color=TEXT_PRIMARY,
                        fg_color=KOPPIE_CYAN,
                        command=self.on_selection_change
                    )
                    r_btn.pack(anchor="w", pady=4)

                if dev.get("packages_needed"):
                    has_actionable = True
            else:
                # Device using in-tree driver
                status_box = ctk.CTkFrame(card, fg_color="#1d2824", corner_radius=6)
                status_box.pack(fill="x", padx=16, pady=(0, 12))

                status_txt = dev.get("status_text", "Using standard Linux driver.")
                st_lbl = ctk.CTkLabel(
                    status_box,
                    text=f"✓  {status_txt}",
                    font=("Ubuntu", 12),
                    text_color=SUCCESS_GREEN,
                    anchor="w"
                )
                st_lbl.pack(padx=12, pady=8, anchor="w")

        if not has_actionable:
            self.apply_btn.configure(state="disabled")

    def on_selection_change(self):
        # Enable Apply Changes if user selects an uninstalled driver
        needs_install = False
        for idx, dev in enumerate(self.devices):
            if idx in self.option_vars and dev.get("options"):
                chosen_idx = self.option_vars[idx].get()
                chosen_opt = dev["options"][chosen_idx]
                if not chosen_opt.get("installed") and chosen_opt.get("packages"):
                    needs_install = True

        self.apply_btn.configure(state="normal" if needs_install else "disabled")

    def apply_changes(self):
        packages_to_install = []
        for idx, dev in enumerate(self.devices):
            if idx in self.option_vars and dev.get("options"):
                chosen_idx = self.option_vars[idx].get()
                chosen_opt = dev["options"][chosen_idx]
                if not chosen_opt.get("installed") and chosen_opt.get("packages"):
                    packages_to_install.extend(chosen_opt["packages"])

        if not packages_to_install:
            return

        pkgs_str = " ".join(packages_to_install)
        confirm = messagebox.askyesno(
            "Apply Changes",
            f"The following packages will be installed:\n\n{pkgs_str}\n\nDo you want to continue?"
        )
        if not confirm:
            return

        self.apply_btn.configure(state="disabled", text="Installing...")
        self.scan_btn.configure(state="disabled")

        def _install_worker():
            cmd = ["pkexec", "pacman", "-S", "--needed", "--noconfirm"] + packages_to_install
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                self.after(0, lambda: messagebox.showinfo(
                    "Success",
                    "Drivers installed successfully!\nA system restart may be required for changes to take effect."
                ))
            else:
                self.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Failed to install driver.\n\n{proc.stderr}"
                ))
            self.after(0, self.scan_async)

        threading.Thread(target=_install_worker, daemon=True).start()


def check_polkit_auth():
    try:
        res = subprocess.run(["pkexec", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            sys.exit(0)
    except Exception:
        pass


if __name__ == "__main__":
    check_polkit_auth()
    app = KoppieDriverManager()
    app.mainloop()
