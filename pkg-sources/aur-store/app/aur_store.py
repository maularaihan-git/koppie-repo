#!/usr/bin/env python3
import subprocess
import threading
import os
import sys
import re
from pathlib import Path

# Ensure bundled libraries (customtkinter, etc.) are available
CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if LIB_DIR.exists():
    sys.path.insert(0, str(LIB_DIR))

ASSETS_DIR = CURRENT_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "aur-store.png"

import customtkinter as ctk
from tkinter import messagebox

# Set modern dark styling
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class YayStoreApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AUR Store")
        # Optimized size for standard laptops & displays (fits cleanly in 1280x800 and 1080p)
        self.geometry("860x650")
        self.minsize(760, 520)

        # Set window icon if available
        if LOGO_PATH.exists():
            try:
                from PIL import ImageTk
                self._icon_img = ImageTk.PhotoImage(file=str(LOGO_PATH))
                self.iconphoto(False, self._icon_img)
            except Exception:
                pass

        # Fluent / Modern dark aesthetic
        self.c_bg = "#1e1e24"              # Deep modern surface
        self.c_header = "#26262e"          # Header surface
        self.c_card = "#2b2b34"            # Tile surface
        self.c_card_border = "#3a3a46"     # Border highlight
        self.c_entry_bg = "#16161a"        # Input field
        self.c_text_bright = "#ffffff"     # White
        self.c_text_sub = "#d1d5db"        # Light Gray
        self.c_text_muted = "#9ca3af"      # Secondary info
        
        # Action colors
        self.c_btn_install = "#2563eb"     # Blue
        self.c_btn_install_h = "#1d4ed8"
        self.c_btn_installed = "#059669"   # Emerald
        self.c_btn_uninstall = "#dc2626"   # Crimson
        self.c_btn_uninstall_h = "#b91c1c"
        self.c_btn_progress = "#d97706"    # Amber

        self.configure(fg_color=self.c_bg)

        self.is_searching = False
        self.is_busy = False
        self.is_alive = True
        self.package_buttons = {}  # {pkg_name: ctk.CTkButton}
        self.active_progress_val = 0.0

        # Handle window close gracefully
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()
        # Default startup search
        self.after(200, lambda: self.search_packages("firefox"))

    def on_close(self):
        self.is_alive = False
        self.destroy()

    def _build_ui(self):
        # 1. TOP HEADER & TITLE
        top_container = ctk.CTkFrame(self, fg_color=self.c_header, corner_radius=0)
        top_container.pack(fill="x", pady=(0, 10))

        top_inner = ctk.CTkFrame(top_container, fg_color="transparent")
        top_inner.pack(fill="x", padx=20, pady=12)

        # Header with Logo + Title
        title_row = ctk.CTkFrame(top_inner, fg_color="transparent")
        title_row.pack(anchor="w", fill="x")

        if LOGO_PATH.exists():
            try:
                from PIL import Image
                pil_logo = Image.open(LOGO_PATH).resize((36, 36), Image.Resampling.LANCZOS)
                self.top_logo_img = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(36, 36))
                logo_lbl = ctk.CTkLabel(title_row, image=self.top_logo_img, text="")
                logo_lbl.pack(side="left", padx=(0, 10))
            except Exception:
                pass

        title_box = ctk.CTkFrame(title_row, fg_color="transparent")
        title_box.pack(side="left", fill="y")

        title_label = ctk.CTkLabel(
            title_box,
            text="AUR Store",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.c_text_bright
        )
        title_label.pack(anchor="w")

        subtitle_label = ctk.CTkLabel(
            title_box,
            text="Discover, install, and manage Arch Linux and AUR software.",
            font=ctk.CTkFont(size=12),
            text_color=self.c_text_sub
        )
        subtitle_label.pack(anchor="w")

        # 2. SEARCH BAR
        search_wrapper = ctk.CTkFrame(self, fg_color="transparent")
        search_wrapper.pack(fill="x", padx=20, pady=(0, 10))

        search_bar_frame = ctk.CTkFrame(search_wrapper, fg_color="transparent")
        search_bar_frame.pack(fill="x")

        self.search_entry = ctk.CTkEntry(
            search_bar_frame,
            placeholder_text="Search packages (e.g. discord, vlc, steam, fastfetch)...",
            height=40,
            corner_radius=10,
            font=ctk.CTkFont(size=14),
            fg_color=self.c_entry_bg,
            border_color=self.c_card_border,
            border_width=1,
            text_color=self.c_text_bright
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<Return>", lambda e: self.on_search_click())

        self.search_btn = ctk.CTkButton(
            search_bar_frame,
            text="Search",
            width=110,
            height=40,
            corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.c_btn_install,
            hover_color=self.c_btn_install_h,
            command=self.on_search_click
        )
        self.search_btn.pack(side="left")

        # 3. STATUS / RESULTS COUNT HEADER
        self.status_label = ctk.CTkLabel(
            self,
            text="Ready to search.",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.c_text_sub,
            anchor="w"
        )
        self.status_label.pack(fill="x", padx=24, pady=(0, 6))

        # 4. CARDS SCROLLABLE CONTAINER
        self.cards_scroll = ctk.CTkScrollableFrame(
            self,
            corner_radius=12,
            fg_color="#18181e",
            border_width=1,
            border_color="#2b2b36"
        )
        self.cards_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # 5. BOTTOM SYSTEM & PROGRESS BAR
        self.bottom_bar = ctk.CTkFrame(self, fg_color=self.c_header, corner_radius=10)
        self.bottom_bar.pack(fill="x", padx=20, pady=(0, 10))

        bottom_inner = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        bottom_inner.pack(fill="x", padx=16, pady=10)

        status_row = ctk.CTkFrame(bottom_inner, fg_color="transparent")
        status_row.pack(fill="x", pady=(0, 6))

        self.indicator_dot = ctk.CTkLabel(
            status_row,
            text="●",
            font=ctk.CTkFont(size=16),
            text_color="#10b981"
        )
        self.indicator_dot.pack(side="left", padx=(0, 8))

        self.indicator_text = ctk.CTkLabel(
            status_row,
            text="System ready.",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.c_text_bright
        )
        self.indicator_text.pack(side="left")

        self.percent_text = ctk.CTkLabel(
            status_row,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#fbbf24"
        )
        self.percent_text.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            bottom_inner,
            height=8,
            corner_radius=4,
            progress_color="#2563eb",
            fg_color="#374151"
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0.0)

    def on_search_click(self):
        query = self.search_entry.get().strip()
        if not query:
            self.status_label.configure(text="Please type an application name to search.", text_color="#f87171")
            return
        if self.is_searching:
            return
        self.search_packages(query)

    def _rank_packages(self, items, query):
        q = query.lower()

        def score(item):
            name = item["name"].lower()
            is_official = item["repo"].lower() in ["extra", "core", "multilib"]

            if name == q:
                tier = 0
            elif name.startswith(q + "-") or name.startswith(q + "_") or name.startswith(q):
                tier = 1
            elif q in name:
                tier = 2
            else:
                tier = 3

            repo_priority = 0 if is_official else 1
            length_penalty = len(name)

            return (tier, repo_priority, length_penalty, name)

        return sorted(items, key=score)

    def search_packages(self, query):
        self.is_searching = True
        self.search_btn.configure(state="disabled", text="Searching...")
        self.status_label.configure(text=f"Searching for '{query}'...", text_color=self.c_text_sub)
        self.indicator_text.configure(text=f"Searching packages for '{query}'...")
        self.indicator_dot.configure(text_color="#60a5fa")
        self.progress_bar.set(0.4)
        self.percent_text.configure(text="")

        for widget in self.cards_scroll.winfo_children():
            widget.destroy()
        self.package_buttons.clear()

        loading_box = ctk.CTkFrame(self.cards_scroll, fg_color="transparent")
        loading_box.pack(pady=40)

        ctk.CTkLabel(
            loading_box,
            text="Searching Packages...",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.c_text_bright
        ).pack()

        ctk.CTkLabel(
            loading_box,
            text="Retrieving package list from Official Arch & AUR repos...",
            font=ctk.CTkFont(size=13),
            text_color=self.c_text_muted
        ).pack(pady=6)

        def worker():
            items = []
            try:
                proc = subprocess.run(
                    ["yay", "-Ss", query],
                    capture_output=True,
                    text=True,
                    timeout=35
                )
                lines = proc.stdout.splitlines()
                idx = 0
                while idx < len(lines):
                    line = lines[idx].strip()
                    if not line or line.startswith("->"):
                        idx += 1
                        continue

                    if "/" in line:
                        first_line = line
                        desc = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
                        idx += 2

                        parts = first_line.split()
                        if parts:
                            repo_pkg = parts[0]
                            repo, pkg_name = repo_pkg.split("/", 1) if "/" in repo_pkg else ("repo", repo_pkg)
                            version = parts[1] if len(parts) > 1 else "Latest"
                            is_installed = "[installed]" in first_line.lower() or "(installed)" in first_line.lower()

                            items.append({
                                "repo": repo,
                                "name": pkg_name,
                                "version": version,
                                "desc": desc,
                                "installed": is_installed
                            })
                    else:
                        idx += 1
            except Exception:
                pass

            if not self.is_alive:
                return

            sorted_items = self._rank_packages(items, query)
            self.after(0, lambda: self._render_results(query, sorted_items))

        threading.Thread(target=worker, daemon=True).start()

    def _render_results(self, query, items):
        if not self.is_alive:
            return

        self.is_searching = False
        self.search_btn.configure(state="normal", text="Search")
        self.progress_bar.set(0.0)

        for widget in self.cards_scroll.winfo_children():
            widget.destroy()
        self.package_buttons.clear()

        if not items:
            self.status_label.configure(text=f"No results found for '{query}'.", text_color="#f87171")
            self.indicator_text.configure(text="Search completed. No matches found.")
            self.indicator_dot.configure(text_color=self.c_text_muted)

            empty_frame = ctk.CTkFrame(self.cards_scroll, fg_color="transparent")
            empty_frame.pack(pady=40)
            ctk.CTkLabel(
                empty_frame,
                text="No Applications Found",
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color=self.c_text_bright
            ).pack()
            ctk.CTkLabel(
                empty_frame,
                text=f"No packages matched '{query}'. Try a different keyword.",
                font=ctk.CTkFont(size=13),
                text_color=self.c_text_sub,
                justify="center"
            ).pack(pady=8)
            return

        self.status_label.configure(
            text=f"Showing results for '{query}':",
            text_color=self.c_text_bright
        )
        self.indicator_text.configure(text=f"Found {len(items)} packages for '{query}'. Ready to install.")
        self.indicator_dot.configure(text_color="#10b981")

        for item in items[:40]:
            self._create_package_card(item)

    def _create_package_card(self, item):
        card = ctk.CTkFrame(
            self.cards_scroll,
            corner_radius=10,
            fg_color=self.c_card,
            border_width=1,
            border_color=self.c_card_border
        )
        card.pack(fill="x", padx=6, pady=5)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=14, pady=10)

        # LEFT SIDE
        left_side = ctk.CTkFrame(content, fg_color="transparent")
        left_side.pack(side="left", fill="both", expand=True)

        name_row = ctk.CTkFrame(left_side, fg_color="transparent")
        name_row.pack(anchor="w", fill="x")

        name_lbl = ctk.CTkLabel(
            name_row,
            text=item["name"],
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.c_text_bright
        )
        name_lbl.pack(side="left", padx=(0, 10))

        # UNINSTALL BUTTON BESIDE APP NAME
        if item["installed"]:
            uninstall_btn = ctk.CTkButton(
                name_row,
                text="Uninstall",
                width=80,
                height=26,
                corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=self.c_btn_uninstall,
                hover_color=self.c_btn_uninstall_h,
                text_color="#ffffff",
                command=lambda p=item["name"]: self.confirm_uninstall(p)
            )
            uninstall_btn.pack(side="left", padx=(0, 10))

        # Source badge
        is_official = item["repo"] in ["extra", "core", "multilib"]
        badge_text = "Official Arch" if is_official else "AUR Community"
        badge_bg = "#065f46" if is_official else "#581c87"

        badge = ctk.CTkLabel(
            name_row,
            text=f"  {badge_text}  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=badge_bg,
            corner_radius=6,
            text_color="#ffffff"
        )
        badge.pack(side="left")

        # Description
        desc_text = item["desc"] if item["desc"] else "No description available."
        desc_lbl = ctk.CTkLabel(
            left_side,
            text=desc_text,
            font=ctk.CTkFont(size=12),
            text_color=self.c_text_sub,
            anchor="w",
            justify="left",
            wraplength=480
        )
        desc_lbl.pack(anchor="w", pady=(4, 0))

        # RIGHT SIDE
        right_side = ctk.CTkFrame(content, fg_color="transparent")
        right_side.pack(side="right", padx=(10, 0))

        ver_lbl = ctk.CTkLabel(
            right_side,
            text=f"Version:\n{item['version']}",
            font=ctk.CTkFont(size=11),
            text_color=self.c_text_muted,
            justify="center"
        )
        ver_lbl.pack(side="left", padx=(0, 14))

        if item["installed"]:
            main_btn = ctk.CTkButton(
                right_side,
                text="✓ Installed",
                width=110,
                height=34,
                corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=self.c_btn_installed,
                hover_color="#047857",
                command=lambda p=item["name"]: self.confirm_install(p, is_reinstall=True)
            )
        else:
            main_btn = ctk.CTkButton(
                right_side,
                text="Install",
                width=110,
                height=34,
                corner_radius=8,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=self.c_btn_install,
                hover_color=self.c_btn_install_h,
                command=lambda p=item["name"]: self.confirm_install(p, is_reinstall=False)
            )
        main_btn.pack(side="left")

        self.package_buttons[item["name"]] = main_btn

    def confirm_install(self, pkg_name, is_reinstall=False):
        if self.is_busy:
            messagebox.showinfo("Busy", "Another installation or removal task is currently in progress.")
            return

        modal = ctk.CTkToplevel(self)
        modal.title(f"Install {pkg_name}")
        modal.geometry("420x240")
        modal.configure(fg_color=self.c_bg)
        modal.transient(self)
        modal.grab_set()

        inner = ctk.CTkFrame(modal, fg_color=self.c_card, corner_radius=12)
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        title_msg = f"Reinstall {pkg_name}?" if is_reinstall else f"Install {pkg_name}?"
        ctk.CTkLabel(
            inner,
            text=title_msg,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.c_text_bright
        ).pack(pady=(12, 4))

        ctk.CTkLabel(
            inner,
            text=f"Package: {pkg_name}\n\nEnter administrator password (leave blank if not needed):",
            font=ctk.CTkFont(size=12),
            text_color=self.c_text_sub,
            justify="center"
        ).pack(pady=4)

        pwd_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Password",
            show="*",
            width=280,
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=13),
            fg_color=self.c_entry_bg,
            border_color=self.c_card_border
        )
        pwd_entry.pack(pady=8)
        pwd_entry.focus_set()

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(pady=(10, 8))

        def on_proceed():
            pwd = pwd_entry.get()
            modal.destroy()
            self._run_task("install", pkg_name, pwd)

        cancel_btn = ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=100,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#4b5563",
            hover_color="#374151",
            command=modal.destroy
        )
        cancel_btn.pack(side="left", padx=6)

        confirm_btn = ctk.CTkButton(
            btn_row,
            text="Install",
            width=120,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.c_btn_install,
            hover_color=self.c_btn_install_h,
            command=on_proceed
        )
        confirm_btn.pack(side="left", padx=6)

    def confirm_uninstall(self, pkg_name):
        if self.is_busy:
            messagebox.showinfo("Busy", "Another operation is currently running.")
            return

        modal = ctk.CTkToplevel(self)
        modal.title(f"Uninstall {pkg_name}")
        modal.geometry("420x240")
        modal.configure(fg_color=self.c_bg)
        modal.transient(self)
        modal.grab_set()

        inner = ctk.CTkFrame(modal, fg_color=self.c_card, corner_radius=12)
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            inner,
            text="Uninstall Application?",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ef4444"
        ).pack(pady=(12, 4))

        ctk.CTkLabel(
            inner,
            text=f"Are you sure you want to remove '{pkg_name}'?\nEnter administrator password:",
            font=ctk.CTkFont(size=12),
            text_color=self.c_text_sub,
            justify="center"
        ).pack(pady=4)

        pwd_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Password",
            show="*",
            width=280,
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=13),
            fg_color=self.c_entry_bg,
            border_color=self.c_card_border
        )
        pwd_entry.pack(pady=8)
        pwd_entry.focus_set()

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(pady=(10, 8))

        def on_proceed():
            pwd = pwd_entry.get()
            modal.destroy()
            self._run_task("uninstall", pkg_name, pwd)

        cancel_btn = ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=100,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#4b5563",
            hover_color="#374151",
            command=modal.destroy
        )
        cancel_btn.pack(side="left", padx=6)

        confirm_btn = ctk.CTkButton(
            btn_row,
            text="Yes, Uninstall",
            width=120,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.c_btn_uninstall,
            hover_color=self.c_btn_uninstall_h,
            command=on_proceed
        )
        confirm_btn.pack(side="left", padx=6)

    def _run_task(self, action_type, pkg_name, password):
        self.is_busy = True
        is_inst = (action_type == "install")
        
        action_verb = "Installing" if is_inst else "Uninstalling"
        self.active_progress_val = 0.1
        self.progress_bar.set(0.1)
        self.progress_bar.configure(progress_color="#d97706")

        target_btn = self.package_buttons.get(pkg_name)
        if target_btn:
            target_btn.configure(
                text="⏳ Working",
                fg_color=self.c_btn_progress,
                hover_color="#b45309",
                state="disabled"
            )

        self.indicator_text.configure(text=f"{action_verb} '{pkg_name}'... Please wait.")
        self.percent_text.configure(text="Working...")
        self.indicator_dot.configure(text_color="#f59e0b")

        def worker():
            if password:
                subprocess.run(
                    ["sudo", "-S", "-v"],
                    input=password + "\n",
                    text=True,
                    capture_output=True
                )

            if is_inst:
                cmd = [
                    "yay", "-S",
                    "--noconfirm",
                    "--answerdiff", "None",
                    "--answerclean", "None",
                    "--answerupgrade", "None",
                    "--needed",
                    pkg_name
                ]
            else:
                cmd = ["yay", "-R", "--noconfirm", pkg_name]

            # Collect output for error reporting
            output_log = []
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            pct_regex = re.compile(r"(\d{1,3})%")

            for line in iter(proc.stdout.readline, ""):
                if not self.is_alive:
                    break
                output_log.append(line)
                m = pct_regex.search(line)
                if m:
                    pct = int(m.group(1))
                    val = max(0.15, min(0.95, pct / 100.0))
                    self.active_progress_val = val
                    if self.is_alive:
                        self.after(0, lambda p=pct, v=val: self._update_ui_progress(pkg_name, action_verb, p, v))
                else:
                    if self.active_progress_val < 0.85:
                        self.active_progress_val += 0.03
                        curr_pct = int(self.active_progress_val * 100)
                        if self.is_alive:
                            self.after(0, lambda p=curr_pct, v=self.active_progress_val: self._update_ui_progress(pkg_name, action_verb, p, v))

            proc.stdout.close()
            code = proc.wait()

            def finish():
                if not self.is_alive:
                    return

                self.is_busy = False
                if code == 0:
                    self.progress_bar.set(1.0)
                    self.progress_bar.configure(progress_color="#10b981")
                    self.percent_text.configure(text="100%")

                    past_tense = "installed" if is_inst else "uninstalled"
                    self.indicator_text.configure(text=f"Success! '{pkg_name}' was successfully {past_tense}.")
                    self.indicator_dot.configure(text_color="#10b981")

                    if target_btn:
                        target_btn.configure(
                            text="✓ Installed" if is_inst else "Install",
                            fg_color=self.c_btn_installed if is_inst else self.c_btn_install,
                            state="normal"
                        )

                    try:
                        messagebox.showinfo("Success", f"'{pkg_name}' was successfully {past_tense}!")
                    except Exception:
                        pass

                    q = self.search_entry.get().strip()
                    if q and self.is_alive:
                        self.search_packages(q)
                else:
                    self.progress_bar.set(1.0)
                    self.progress_bar.configure(progress_color="#ef4444")
                    self.percent_text.configure(text="Failed")

                    self.indicator_text.configure(text=f"Failed to {action_type} '{pkg_name}'.")
                    self.indicator_dot.configure(text_color="#ef4444")

                    if target_btn:
                        target_btn.configure(
                            text="Retry Install",
                            fg_color=self.c_btn_install,
                            state="normal"
                        )

                    # Filter last meaningful error lines from log
                    raw_lines = [l.strip() for l in output_log if l.strip()]
                    err_snippet = "\n".join(raw_lines[-5:]) if raw_lines else "Unknown error."
                    err_msg = (
                        f"Failed to {action_type} '{pkg_name}'.\n\n"
                        f"Terminal Details:\n{err_snippet}\n\n"
                        f"(Note: Some AUR packages may fail to compile due to broken upstream PKGBUILD/C compiler issues)."
                    )
                    try:
                        messagebox.showerror("Installation Error", err_msg)
                    except Exception:
                        pass

            if self.is_alive:
                self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _update_ui_progress(self, pkg_name, action_verb, pct, val):
        if not self.is_alive:
            return
        self.progress_bar.set(val)
        self.percent_text.configure(text=f"{pct}%")
        self.indicator_text.configure(text=f"{action_verb} '{pkg_name}'... ({pct}%)")

if __name__ == "__main__":
    app = YayStoreApp()
    app.mainloop()
