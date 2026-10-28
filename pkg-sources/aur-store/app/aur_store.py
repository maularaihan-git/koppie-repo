#!/usr/bin/env python3
import subprocess
import threading
import os
import sys
import re
from pathlib import Path
from PIL import Image

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
        self.geometry("1120x840")
        self.minsize(940, 700)

        # Set window icon if available
        if LOGO_PATH.exists():
            try:
                from PIL import ImageTk
                self._icon_img = ImageTk.PhotoImage(file=str(LOGO_PATH))
                self.iconphoto(False, self._icon_img)
            except Exception:
                pass

        # Microsoft Store / Mica dark aesthetic
        self.c_bg = "#202020"              # Deep Mica base
        self.c_header = "#262626"          # Header surface
        self.c_card = "#2b2b2b"            # Acrylic tile surface
        self.c_card_border = "#3a3a3a"     # Translucent border highlight
        self.c_entry_bg = "#1e1e1e"        # Recessed input field
        self.c_text_bright = "#ffffff"     # High readability bold white
        self.c_text_sub = "#d1d5db"        # Clear neutral gray
        self.c_text_muted = "#9ca3af"      # Secondary info
        
        # Action colors
        self.c_btn_install = "#2563eb"     # Royal Fluent Blue
        self.c_btn_install_h = "#1d4ed8"
        self.c_btn_installed = "#059669"   # Clean forest emerald
        self.c_btn_uninstall = "#dc2626"   # Accessible Crimson Red
        self.c_btn_uninstall_h = "#b91c1c"
        self.c_btn_progress = "#d97706"    # Warm Amber for installing state

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
        self.after(250, lambda: self.search_packages("firefox"))

    def on_close(self):
        self.is_alive = False
        self.destroy()

    def _build_ui(self):
        # 1. TOP HEADER & TITLE
        top_container = ctk.CTkFrame(self, fg_color=self.c_header, corner_radius=0)
        top_container.pack(fill="x", pady=(0, 16))

        top_inner = ctk.CTkFrame(top_container, fg_color="transparent")
        top_inner.pack(fill="x", padx=36, pady=24)

        title_label = ctk.CTkLabel(
            top_inner,
            text="AUR Store",
            font=ctk.CTkFont(family="Segoe UI, Inter, sans-serif", size=36, weight="bold"),
            text_color=self.c_text_bright
        )
        title_label.pack(anchor="w")

        subtitle_label = ctk.CTkLabel(
            top_inner,
            text="Discover, install, and manage applications on your Arch Linux system.",
            font=ctk.CTkFont(size=18),
            text_color=self.c_text_sub
        )
        subtitle_label.pack(anchor="w", pady=(4, 0))

        # 2. SEARCH BAR
        search_wrapper = ctk.CTkFrame(self, fg_color="transparent")
        search_wrapper.pack(fill="x", padx=36, pady=(0, 16))

        search_prompt = ctk.CTkLabel(
            search_wrapper,
            text="Search for applications:",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.c_text_bright
        )
        search_prompt.pack(anchor="w", pady=(0, 8))

        search_bar_frame = ctk.CTkFrame(search_wrapper, fg_color="transparent")
        search_bar_frame.pack(fill="x")

        self.search_entry = ctk.CTkEntry(
            search_bar_frame,
            placeholder_text="Type an app name (e.g. discord, base-devel, firefox, vlc, steam)...",
            height=60,
            corner_radius=14,
            font=ctk.CTkFont(size=20),
            fg_color=self.c_entry_bg,
            border_color=self.c_card_border,
            border_width=2,
            text_color=self.c_text_bright
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 14))
        self.search_entry.bind("<Return>", lambda e: self.on_search_click())

        self.search_btn = ctk.CTkButton(
            search_bar_frame,
            text="Search",
            width=180,
            height=60,
            corner_radius=14,
            font=ctk.CTkFont(size=20, weight="bold"),
            fg_color=self.c_btn_install,
            hover_color=self.c_btn_install_h,
            command=self.on_search_click
        )
        self.search_btn.pack(side="left")

        # 3. STATUS / RESULTS COUNT HEADER
        self.status_label = ctk.CTkLabel(
            self,
            text="Ready to search.",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.c_text_sub,
            anchor="w"
        )
        self.status_label.pack(fill="x", padx=40, pady=(0, 10))

        # 4. CARDS SCROLLABLE CONTAINER
        self.cards_scroll = ctk.CTkScrollableFrame(
            self,
            corner_radius=18,
            fg_color="#181818",
            border_width=2,
            border_color="#2e2e2e"
        )
        self.cards_scroll.pack(fill="both", expand=True, padx=36, pady=(0, 16))

        # 5. BOTTOM SYSTEM & PROGRESS BAR
        self.bottom_bar = ctk.CTkFrame(self, fg_color=self.c_header, corner_radius=16)
        self.bottom_bar.pack(fill="x", padx=36, pady=(0, 18))

        bottom_inner = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        bottom_inner.pack(fill="x", padx=24, pady=16)

        status_row = ctk.CTkFrame(bottom_inner, fg_color="transparent")
        status_row.pack(fill="x", pady=(0, 8))

        self.indicator_dot = ctk.CTkLabel(
            status_row,
            text="●",
            font=ctk.CTkFont(size=22),
            text_color="#10b981"
        )
        self.indicator_dot.pack(side="left", padx=(0, 10))

        self.indicator_text = ctk.CTkLabel(
            status_row,
            text="System ready.",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=self.c_text_bright
        )
        self.indicator_text.pack(side="left")

        self.percent_text = ctk.CTkLabel(
            status_row,
            text="",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#fbbf24"
        )
        self.percent_text.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            bottom_inner,
            height=14,
            corner_radius=7,
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
        loading_box.pack(pady=70)

        ctk.CTkLabel(
            loading_box,
            text="Loading Applications...",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=self.c_text_bright
        ).pack()

        ctk.CTkLabel(
            loading_box,
            text="Please wait a moment while we retrieve the latest information.",
            font=ctk.CTkFont(size=18),
            text_color=self.c_text_muted
        ).pack(pady=8)

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
            empty_frame.pack(pady=70)
            ctk.CTkLabel(
                empty_frame,
                text="No Applications Found",
                font=ctk.CTkFont(size=26, weight="bold"),
                text_color=self.c_text_bright
            ).pack()
            ctk.CTkLabel(
                empty_frame,
                text=f"We couldn't find any packages matching '{query}'.\nPlease check the spelling or try a different keyword.",
                font=ctk.CTkFont(size=18),
                text_color=self.c_text_sub,
                justify="center"
            ).pack(pady=12)
            return

        self.status_label.configure(
            text=f"Showing top results for '{query}':",
            text_color=self.c_text_bright
        )
        self.indicator_text.configure(text=f"Found {len(items)} packages for '{query}'. Ready to install.")
        self.indicator_dot.configure(text_color="#10b981")

        for item in items[:30]:
            self._create_package_card(item)

    def _create_package_card(self, item):
        card = ctk.CTkFrame(
            self.cards_scroll,
            corner_radius=16,
            fg_color=self.c_card,
            border_width=1,
            border_color=self.c_card_border
        )
        card.pack(fill="x", padx=12, pady=9)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=18)

        # LEFT SIDE
        left_side = ctk.CTkFrame(content, fg_color="transparent")
        left_side.pack(side="left", fill="both", expand=True)

        name_row = ctk.CTkFrame(left_side, fg_color="transparent")
        name_row.pack(anchor="w", fill="x")

        name_lbl = ctk.CTkLabel(
            name_row,
            text=item["name"],
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.c_text_bright
        )
        name_lbl.pack(side="left", padx=(0, 12))

        # UNINSTALL BUTTON BESIDE APP NAME
        if item["installed"]:
            uninstall_btn = ctk.CTkButton(
                name_row,
                text="Uninstall",
                width=110,
                height=34,
                corner_radius=8,
                font=ctk.CTkFont(size=14, weight="bold"),
                fg_color=self.c_btn_uninstall,
                hover_color=self.c_btn_uninstall_h,
                text_color="#ffffff",
                command=lambda p=item["name"]: self.confirm_uninstall(p)
            )
            uninstall_btn.pack(side="left", padx=(0, 12))

        # Source badge
        is_official = item["repo"] in ["extra", "core", "multilib"]
        badge_text = "Official Arch" if is_official else "AUR Community"
        badge_bg = "#065f46" if is_official else "#581c87"

        badge = ctk.CTkLabel(
            name_row,
            text=f"  {badge_text}  ",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=badge_bg,
            corner_radius=7,
            text_color="#ffffff"
        )
        badge.pack(side="left")

        # Description
        desc_text = item["desc"] if item["desc"] else "No detailed description available."
        desc_lbl = ctk.CTkLabel(
            left_side,
            text=desc_text,
            font=ctk.CTkFont(size=16),
            text_color=self.c_text_sub,
            anchor="w",
            justify="left",
            wraplength=580
        )
        desc_lbl.pack(anchor="w", pady=(8, 0))

        # RIGHT SIDE
        right_side = ctk.CTkFrame(content, fg_color="transparent")
        right_side.pack(side="right", padx=(16, 0))

        ver_lbl = ctk.CTkLabel(
            right_side,
            text=f"Version:\n{item['version']}",
            font=ctk.CTkFont(size=15),
            text_color=self.c_text_muted,
            justify="center"
        )
        ver_lbl.pack(side="left", padx=(0, 20))

        if item["installed"]:
            main_btn = ctk.CTkButton(
                right_side,
                text="✓ Installed",
                width=165,
                height=50,
                corner_radius=12,
                font=ctk.CTkFont(size=17, weight="bold"),
                fg_color=self.c_btn_installed,
                hover_color="#047857",
                command=lambda p=item["name"]: self.confirm_install(p, is_reinstall=True)
            )
        else:
            main_btn = ctk.CTkButton(
                right_side,
                text="Install",
                width=165,
                height=50,
                corner_radius=12,
                font=ctk.CTkFont(size=18, weight="bold"),
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
        modal.title("Install Package")
        modal.geometry("540x350")
        modal.configure(fg_color=self.c_bg)
        modal.transient(self)
        modal.grab_set()

        inner = ctk.CTkFrame(modal, fg_color=self.c_card, corner_radius=16)
        inner.pack(fill="both", expand=True, padx=22, pady=22)

        title_msg = f"Reinstall {pkg_name}?" if is_reinstall else f"Install {pkg_name}?"
        ctk.CTkLabel(
            inner,
            text=title_msg,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.c_text_bright
        ).pack(pady=(18, 6))

        ctk.CTkLabel(
            inner,
            text=f"Package: {pkg_name}\n\nEnter administrator password if required by system:",
            font=ctk.CTkFont(size=16),
            text_color=self.c_text_sub,
            justify="center"
        ).pack(pady=8)

        pwd_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Password (leave empty if not needed)",
            show="*",
            width=360,
            height=50,
            corner_radius=10,
            font=ctk.CTkFont(size=16),
            fg_color=self.c_entry_bg,
            border_color=self.c_card_border
        )
        pwd_entry.pack(pady=10)
        pwd_entry.focus_set()

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(pady=(16, 12))

        def on_proceed():
            pwd = pwd_entry.get()
            modal.destroy()
            self._run_task("install", pkg_name, pwd)

        cancel_btn = ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=130,
            height=48,
            corner_radius=10,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#4b5563",
            hover_color="#374151",
            command=modal.destroy
        )
        cancel_btn.pack(side="left", padx=8)

        confirm_btn = ctk.CTkButton(
            btn_row,
            text="Confirm & Install",
            width=180,
            height=48,
            corner_radius=10,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=self.c_btn_install,
            hover_color=self.c_btn_install_h,
            command=on_proceed
        )
        confirm_btn.pack(side="left", padx=8)

    def confirm_uninstall(self, pkg_name):
        if self.is_busy:
            messagebox.showinfo("Busy", "Another operation is currently running.")
            return

        modal = ctk.CTkToplevel(self)
        modal.title(f"Uninstall {pkg_name}")
        modal.geometry("540x350")
        modal.configure(fg_color=self.c_bg)
        modal.transient(self)
        modal.grab_set()

        inner = ctk.CTkFrame(modal, fg_color=self.c_card, corner_radius=16)
        inner.pack(fill="both", expand=True, padx=22, pady=22)

        ctk.CTkLabel(
            inner,
            text=f"Uninstall Application?",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#ef4444"
        ).pack(pady=(18, 6))

        ctk.CTkLabel(
            inner,
            text=f"Are you sure you want to remove '{pkg_name}'?\nEnter administrator password if required:",
            font=ctk.CTkFont(size=16),
            text_color=self.c_text_sub,
            justify="center"
        ).pack(pady=8)

        pwd_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Password (leave blank if not needed)",
            show="*",
            width=360,
            height=50,
            corner_radius=10,
            font=ctk.CTkFont(size=16),
            fg_color=self.c_entry_bg,
            border_color=self.c_card_border
        )
        pwd_entry.pack(pady=10)
        pwd_entry.focus_set()

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(pady=(16, 12))

        def on_proceed():
            pwd = pwd_entry.get()
            modal.destroy()
            self._run_task("uninstall", pkg_name, pwd)

        cancel_btn = ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=130,
            height=48,
            corner_radius=10,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#4b5563",
            hover_color="#374151",
            command=modal.destroy
        )
        cancel_btn.pack(side="left", padx=8)

        confirm_btn = ctk.CTkButton(
            btn_row,
            text="Yes, Uninstall",
            width=180,
            height=48,
            corner_radius=10,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=self.c_btn_uninstall,
            hover_color=self.c_btn_uninstall_h,
            command=on_proceed
        )
        confirm_btn.pack(side="left", padx=8)

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
                text=f"⏳ {action_verb} 10%",
                fg_color=self.c_btn_progress,
                hover_color="#b45309",
                state="disabled"
            )

        self.indicator_text.configure(text=f"{action_verb} '{pkg_name}'... Please wait.")
        self.percent_text.configure(text="10%")
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

            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            def auto_responder():
                try:
                    for _ in range(10):
                        if proc.poll() is not None:
                            break
                        proc.stdin.write("\n")
                        proc.stdin.flush()
                        threading.Event().wait(1.5)
                except Exception:
                    pass

            threading.Thread(target=auto_responder, daemon=True).start()

            pct_regex = re.compile(r"(\d{1,3})%")

            for line in iter(proc.stdout.readline, ""):
                if not self.is_alive:
                    break
                m = pct_regex.search(line)
                if m:
                    pct = int(m.group(1))
                    val = max(0.15, min(0.95, pct / 100.0))
                    self.active_progress_val = val
                    if self.is_alive:
                        self.after(0, lambda p=pct, v=val: self._update_ui_progress(pkg_name, action_verb, p, v))
                else:
                    if self.active_progress_val < 0.85:
                        self.active_progress_val += 0.04
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

                    try:
                        messagebox.showerror("Error", f"Failed to {action_type} '{pkg_name}'.\nPlease check internet connection or password.")
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

        target_btn = self.package_buttons.get(pkg_name)
        if target_btn:
            target_btn.configure(text=f"⏳ {pct}%")

if __name__ == "__main__":
    app = YayStoreApp()
    app.mainloop()
