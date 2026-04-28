import uuid
import random
import paramiko
import xml.etree.ElementTree as ET
import difflib
import json
import os
import platform
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from urllib.parse import quote

import customtkinter as ctk
import requests
from ncclient import manager
from ncclient.operations import RPCError

requests.packages.urllib3.disable_warnings()

GITHUB_API_URL = "https://api.github.com/repos/MijsBjornPXL/Cisco-CSR1000v/contents/Configs?ref=main"
PROFILE_FILE = "csr1000v_profiles.json"
BACKUP_DIR = "backups"
LOCAL_CONFIG_DIR = "Configs"

RESTCONF_HEADERS = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json"
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class ModernConfigPushGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Cisco Config Deployer - M1jsXploit")
        self.root.geometry("1180x952")
        self.root.minsize(1000, 760)

        self.configs = []
        self.is_loading = False
        self.password_visible = False
        self.profiles = self.load_profiles_from_file()
        os.makedirs(LOCAL_CONFIG_DIR, exist_ok=True)

        self.create_widgets()
        self.load_profile_dropdown()
        self.load_local_configs()

    def create_widgets(self):
        self.main_frame = ctk.CTkFrame(self.root, corner_radius=16)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=8)

        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=22, pady=(22, 8))

        ctk.CTkLabel(
            header_frame,
            text="Cisco Config Deployer",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            header_frame,
            text="Deploy NETCONF XML and RESTCONF JSON configs directly from GitHub",
            font=ctk.CTkFont(size=14),
            text_color="gray70"
        ).pack(anchor="w", pady=(6, 0))

        settings_frame = ctk.CTkFrame(self.main_frame, corner_radius=14, fg_color="#323232")
        settings_frame.pack(fill="x", padx=22, pady=(10, 12))

        ctk.CTkLabel(
            settings_frame,
            text="Profiles",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=18, pady=(18, 8))

        profile_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        profile_row.pack(fill="x", padx=18, pady=(0, 22))

        self.profile_name_entry = ctk.CTkEntry(profile_row, placeholder_text="Profile name")
        self.profile_name_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.profile_var = tk.StringVar(value="No profiles")
        self.profile_dropdown = ctk.CTkOptionMenu(
            profile_row,
            variable=self.profile_var,
            values=["No profiles"],
            width=230
        )
        self.profile_dropdown.pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            profile_row,
            text="💾 Save Profile",
            command=self.save_current_profile,
            height=38,
            fg_color="#7C3AED",
            hover_color="#6D28D9"
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            profile_row,
            text="📂 Load Profile",
            command=self.load_selected_profile,
            height=38,
            fg_color="#0891B2",
            hover_color="#0E7490"
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            profile_row,
            text="🔌 Test Connection",
            command=self.test_connection_threaded,
            height=38,
            fg_color="#2563EB",
            hover_color="#1D4ED8"
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            profile_row,
            text="ℹ️ Get Device Info",
            command=self.get_device_info_threaded,
            height=38,
            fg_color="#0F766E",
            hover_color="#115E59"
        ).pack(side="left")

        divider = ctk.CTkFrame(settings_frame, height=1, fg_color="#4A4A4A")
        divider.pack(fill="x", padx=18, pady=(0, 0))

        ctk.CTkLabel(
            settings_frame,
            text="Target Router Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=18, pady=(0, 8))

        target_grid = ctk.CTkFrame(settings_frame, fg_color="transparent")
        target_grid.pack(fill="x", padx=18, pady=(0, 18))

        labels = ["Host / IP", "Username", "Password", "NETCONF Port", "RESTCONF Port"]

        for i, text in enumerate(labels):
            ctk.CTkLabel(
                target_grid,
                text=text,
                font=ctk.CTkFont(size=12),
                text_color="gray75"
            ).grid(row=0, column=i, sticky="w", padx=8, pady=(0, 4))

        self.host_entry = ctk.CTkEntry(target_grid, placeholder_text="Enter hostname or IP")
        self.host_entry.grid(row=1, column=0, padx=8, pady=(0, 12), sticky="ew")

        self.username_entry = ctk.CTkEntry(target_grid, placeholder_text="Enter username")
        self.username_entry.grid(row=1, column=1, padx=8, pady=(0, 12), sticky="ew")

        password_frame = ctk.CTkFrame(target_grid, fg_color="transparent")
        password_frame.grid(row=1, column=2, padx=8, pady=(0, 12), sticky="ew")
        password_frame.columnconfigure(0, weight=1)

        self.password_entry = ctk.CTkEntry(
            password_frame,
            placeholder_text="Enter password",
            show="*"
        )
        self.password_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.password_toggle_button = ctk.CTkButton(
            password_frame,
            text="👁",
            width=42,
            command=self.toggle_password_visibility,
            fg_color="#444444",
            hover_color="#555555"
        )
        self.password_toggle_button.grid(row=0, column=1)

        self.netconf_port_entry = ctk.CTkEntry(target_grid, placeholder_text="830")
        self.netconf_port_entry.grid(row=1, column=3, padx=8, pady=(0, 12), sticky="ew")

        self.restconf_port_entry = ctk.CTkEntry(target_grid, placeholder_text="443")
        self.restconf_port_entry.grid(row=1, column=4, padx=8, pady=(0, 12), sticky="ew")

        for col in range(5):
            target_grid.columnconfigure(col, weight=1)

        select_frame = ctk.CTkFrame(self.main_frame, corner_radius=14)
        select_frame.pack(fill="x", padx=22, pady=(0, 18))

        ctk.CTkLabel(
            select_frame,
            text="GitHub Config Selection",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=18, pady=(18, 10))

        self.config_var = tk.StringVar()
        self.config_dropdown = ctk.CTkOptionMenu(
            select_frame,
            variable=self.config_var,
            values=["Loading configs..."],
            width=680
        )
        self.config_dropdown.pack(anchor="w", padx=18, pady=(0, 18))

        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=22, pady=(0, 12))

        self.refresh_button = ctk.CTkButton(
            button_frame,
            text="🔄 Refresh Configs",
            command=self.load_configs_threaded,
            height=40,
            fg_color="#7C3AED",
            hover_color="#6D28D9"
        )
        self.refresh_button.pack(side="left", padx=(0, 12))

        self.preview_button = ctk.CTkButton(
            button_frame,
            text="👁 Preview Config",
            command=self.preview_config_threaded,
            height=40,
            fg_color="#0891B2",
            hover_color="#0E7490"
        )
        self.preview_button.pack(side="left", padx=(0, 12))

        self.diff_button = ctk.CTkButton(
            button_frame,
            text="🔍 Diff Viewer",
            command=self.diff_viewer_threaded,
            height=40,
            fg_color="#475569",
            hover_color="#334155"
        )
        self.diff_button.pack(side="left", padx=(0, 12))

        self.push_button = ctk.CTkButton(
            button_frame,
            text="🚀 Push Config",
            command=self.push_config_threaded,
            height=40,
            fg_color="#15803D",
            hover_color="#166534"
        )
        self.push_button.pack(side="left", padx=(0, 12))

        self.export_log_button = ctk.CTkButton(
            button_frame,
            text="📄 Export Log",
            command=self.export_log,
            height=40,
            fg_color="#CA8A04",
            hover_color="#A16207"
        )
        self.export_log_button.pack(side="left", padx=(0, 12))

        self.clear_button = ctk.CTkButton(
            button_frame,
            text="🗑 Clear Log",
            command=self.clear_log,
            height=40,
            fg_color="#444444",
            hover_color="#555555"
        )
        self.clear_button.pack(side="left", padx=(0, 12))

        self.deploy_vm_button = ctk.CTkButton(
            button_frame,
            text="🖥 Deploy Router VM",
            command=self.open_vm_deployer_window,
            height=40,
            fg_color="#9333EA",
            hover_color="#7E22CE"
        )
        self.deploy_vm_button.pack(side="left")

        options_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        options_frame.pack(fill="x", padx=22, pady=(0, 10))

        self.backup_before_deploy_var = tk.BooleanVar(value=True)
        self.backup_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="Backup running-config before deploy",
            variable=self.backup_before_deploy_var
        )
        self.backup_checkbox.pack(anchor="w")

        progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        progress_frame.pack(fill="x", padx=22, pady=(4, 8))

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Ready",
            text_color="gray70",
            font=ctk.CTkFont(size=14)
        )
        self.status_label.pack(anchor="w")

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", pady=(6, 0))
        self.progress_bar.set(0)

        log_frame = ctk.CTkFrame(self.main_frame, corner_radius=14)
        log_frame.pack(fill="both", expand=True, padx=22, pady=(6, 8))

        ctk.CTkLabel(
            log_frame,
            text="Deployment Log",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=18, pady=(18, 10))

        self.log_box = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=13),
            corner_radius=10
        )
        self.log_box.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        footer = ctk.CTkLabel(
            self.main_frame,
            text="Cisco Config Deployer v1.0 | by M1jsXploit",
            font=ctk.CTkFont(size=11),
            text_color="gray55"
        )
        footer.pack(anchor="e", padx=22, pady=(0, 10))

    def load_local_configs(self):
        try:
            self.configs = []
            files = os.listdir(LOCAL_CONFIG_DIR)

            for filename in files:
                if filename.lower().endswith((".xml", ".json")):
                    path = os.path.join(LOCAL_CONFIG_DIR, filename)
                    self.configs.append({
                        "name": filename,
                        "local_path": path,
                        "type": self.get_config_type(filename)
                    })

            if not self.configs:
                self.config_dropdown.configure(values=["No local configs found"])
                self.config_var.set("No local configs found")
                self.log("No local configs found.")
                return

            values = [f"{cfg['name']} ({cfg['type']})" for cfg in self.configs]
            self.config_dropdown.configure(values=values)
            self.config_var.set(values[0])
            self.log(f"Loaded {len(self.configs)} local config(s).")

        except Exception as e:
            self.log(f"Failed loading local configs: {e}")

    def toggle_password_visibility(self):
        self.password_visible = not self.password_visible

        if self.password_visible:
            self.password_entry.configure(show="")
            self.password_toggle_button.configure(text="🙈")
        else:
            self.password_entry.configure(show="*")
            self.password_toggle_button.configure(text="👁")

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.root.update_idletasks()


    def update_last_log_line(self, message):
        timestamp = time.strftime("%H:%M:%S")

        try:
            self.log_box.delete("end-2l", "end-1l")
            self.log_box.insert("end", f"[{timestamp}] {message}\n")
            self.log_box.see("end")
            self.root.update_idletasks()
        except Exception:
            self.log(message)
            
            
    def clear_log(self):
        self.log_box.delete("1.0", "end")

    def set_status(self, message, progress=None):
        self.status_label.configure(text=message)
        if progress is not None:
            self.progress_bar.set(progress)
        self.root.update_idletasks()

    def set_buttons_state(self, state):
        self.refresh_button.configure(state=state)
        self.preview_button.configure(state=state)
        self.diff_button.configure(state=state)
        self.push_button.configure(state=state)
        self.export_log_button.configure(state=state)
        self.clear_button.configure(state=state)
        self.deploy_vm_button.configure(state=state)

    def start_loading(self, message):
        self.is_loading = True
        self.set_status(message, 0)
        self.animate_progress()

    def stop_loading(self, message="Ready", progress=1):
        self.is_loading = False
        self.set_status(message, progress)

    def animate_progress(self):
        if self.is_loading:
            current = self.progress_bar.get()
            new_value = current + 0.03
            if new_value > 0.95:
                new_value = 0.15
            self.progress_bar.set(new_value)
            self.root.after(120, self.animate_progress)

    def get_router_settings(self):
        host = self.host_entry.get().strip()
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        netconf_port = self.netconf_port_entry.get().strip()
        restconf_port = self.restconf_port_entry.get().strip()

        if not host:
            raise ValueError("Host/IP is required.")
        if not username:
            raise ValueError("Username is required.")
        if not password:
            raise ValueError("Password is required.")
        if not netconf_port.isdigit():
            raise ValueError("NETCONF port must be a number.")
        if not restconf_port.isdigit():
            raise ValueError("RESTCONF port must be a number.")

        return {
            "host": host,
            "username": username,
            "password": password,
            "netconf_port": int(netconf_port),
            "restconf_port": int(restconf_port),
            "restconf_base_url": f"https://{host}:{restconf_port}"
        }

    def load_profiles_from_file(self):
        if not os.path.exists(PROFILE_FILE):
            return {}

        try:
            with open(PROFILE_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return {}

    def save_profiles_to_file(self):
        with open(PROFILE_FILE, "w", encoding="utf-8") as file:
            json.dump(self.profiles, file, indent=4)

    def load_profile_dropdown(self):
        names = list(self.profiles.keys())

        if not names:
            self.profile_dropdown.configure(values=["No profiles"])
            self.profile_var.set("No profiles")
            return

        self.profile_dropdown.configure(values=names)
        self.profile_var.set(names[0])

    def save_current_profile(self):
        name = self.profile_name_entry.get().strip()

        if not name:
            messagebox.showerror("Profile Error", "Profile name is required.")
            return

        self.profiles[name] = {
            "host": self.host_entry.get().strip(),
            "username": self.username_entry.get().strip(),
            "password": self.password_entry.get(),
            "netconf_port": self.netconf_port_entry.get().strip(),
            "restconf_port": self.restconf_port_entry.get().strip()
        }

        self.save_profiles_to_file()
        self.load_profile_dropdown()
        self.profile_var.set(name)
        self.log(f"Profile saved with password: {name}")

    def load_selected_profile(self):
        name = self.profile_var.get()

        if name not in self.profiles:
            messagebox.showerror("Profile Error", "No valid profile selected.")
            return

        profile = self.profiles[name]

        self.host_entry.delete(0, "end")
        self.host_entry.insert(0, profile.get("host", ""))

        self.username_entry.delete(0, "end")
        self.username_entry.insert(0, profile.get("username", ""))

        self.password_entry.delete(0, "end")
        self.password_entry.insert(0, profile.get("password", ""))
        self.password_entry.configure(show="*")
        self.password_visible = False
        self.password_toggle_button.configure(text="👁")

        self.netconf_port_entry.delete(0, "end")
        self.netconf_port_entry.insert(0, profile.get("netconf_port", "830"))

        self.restconf_port_entry.delete(0, "end")
        self.restconf_port_entry.insert(0, profile.get("restconf_port", "443"))

        self.log(f"Profile loaded with password: {name}")

    def load_configs_threaded(self):
        threading.Thread(target=self.load_configs, daemon=True).start()

    def load_configs(self):
        try:
            self.set_buttons_state("disabled")
            self.start_loading("Syncing configs from GitHub...")
            self.log("Fetching configs from GitHub...")

            response = requests.get(GITHUB_API_URL, timeout=30)
            response.raise_for_status()

            files = response.json()
            downloaded = 0

            for item in files:
                if item["type"] == "file" and item["name"].lower().endswith((".xml", ".json")):
                    file_resp = requests.get(item["download_url"], timeout=30)
                    file_resp.raise_for_status()

                    local_path = os.path.join(LOCAL_CONFIG_DIR, item["name"])

                    with open(local_path, "w", encoding="utf-8") as f:
                        f.write(file_resp.text)

                    downloaded += 1

            self.log(f"Downloaded {downloaded} config(s) from GitHub.")
            self.load_local_configs()
            self.stop_loading("Configs refreshed.", 1)

        except Exception as error:
            self.stop_loading("Refresh failed.", 0)
            self.log(f"GitHub sync failed: {error}")
            messagebox.showerror("GitHub Error", str(error))

        finally:
            self.set_buttons_state("normal")

    def get_config_type(self, filename):
        if filename.lower().endswith(".xml"):
            return "NETCONF"
        if filename.lower().endswith(".json"):
            return "RESTCONF"
        return "UNKNOWN"

    def get_selected_config(self):
        selected_name = self.config_var.get()

        for config in self.configs:
            display_name = f"{config['name']} ({config['type']})"
            if display_name == selected_name:
                return config

        raise ValueError("No valid config selected.")

    def download_selected_config(self, config):
        path = config["local_path"]

        self.log(f"Loading local config: {config['name']}")
        self.set_status(f"Loading {config['name']}...", 0.25)

        with open(path, "r", encoding="utf-8") as file:
            content = file.read().strip()

        if config["type"] == "NETCONF" and "noshutdown" in content.lower():
            raise ValueError("Local XML contains unsupported <noshutdown/> tag.")

        return content

    def preview_config_threaded(self):
        threading.Thread(target=self.preview_config, daemon=True).start()

    def preview_config(self):
        try:
            self.set_buttons_state("disabled")
            config = self.get_selected_config()

            self.start_loading(f"{config['type']} detected - previewing {config['name']}...")
            self.log(f"{config['type']} detected based on file extension.")

            content = self.download_selected_config(config)

            self.root.after(
                0,
                lambda: self.show_preview_window(config["name"], config["type"], content)
            )

            self.stop_loading("Preview loaded.", 1)

        except Exception as error:
            self.stop_loading("Preview failed.", 0)
            self.log(f"Preview failed: {error}")
            messagebox.showerror("Preview Error", str(error))

        finally:
            self.root.after(0, lambda: self.set_buttons_state("normal"))

    def show_preview_window(self, filename, config_type, content):
        preview = ctk.CTkToplevel(self.root)

        preview.transient(self.root)
        preview.lift()
        preview.focus_force()
        preview.attributes("-topmost", True)
        preview.after(300, lambda: preview.attributes("-topmost", False))

        preview.title(f"Preview - {filename}")
        preview.geometry("950x700")
        preview.minsize(800, 500)

        header = ctk.CTkFrame(preview, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            header,
            text=f"Preview: {filename}",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text=f"Type: {config_type}",
            text_color="gray70"
        ).pack(anchor="w", pady=(4, 0))

        textbox = ctk.CTkTextbox(
            preview,
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=10
        )
        textbox.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        pretty_content = self.format_preview_content(content, config_type)
        textbox.insert("1.0", pretty_content)
        textbox.configure(state="disabled")

        footer = ctk.CTkFrame(preview, fg_color="transparent")
        footer.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(
            footer,
            text="📋 Copy to Clipboard",
            command=lambda: self.copy_to_clipboard(pretty_content),
            height=36,
            fg_color="#0891B2",
            hover_color="#0E7490"
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            footer,
            text="Close",
            command=preview.destroy,
            height=36,
            fg_color="#444444",
            hover_color="#555555"
        ).pack(side="left")

    def format_preview_content(self, content, config_type):
        if config_type == "RESTCONF":
            try:
                parsed = json.loads(content)
                return json.dumps(parsed, indent=4)
            except Exception:
                return content
        return content

    def copy_to_clipboard(self, content):
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.log("Preview content copied to clipboard.")

    def test_connection_threaded(self):
        threading.Thread(target=self.test_connection, daemon=True).start()

    def test_connection(self):
        try:
            self.set_buttons_state("disabled")
            router = self.get_router_settings()

            self.start_loading("Testing connection...")
            self.log(f"Testing connection to {router['host']}...")

            ping_ok = self.ping_host(router["host"])
            self.log(f"Ping test: {'successful' if ping_ok else 'failed'}")

            self.test_netconf(router)
            self.test_restconf(router)

            self.stop_loading("Connection test completed.", 1)

        except Exception as error:
            self.stop_loading("Connection test failed.", 0)
            self.log(f"Connection test failed: {error}")
            messagebox.showerror("Connection Test Failed", str(error))

        finally:
            self.set_buttons_state("normal")

    def ping_host(self, host):
        param = "-n" if platform.system().lower() == "windows" else "-c"

        result = subprocess.run(
            ["ping", param, "1", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return result.returncode == 0

    def test_netconf(self, router):
        try:
            self.log(f"Testing NETCONF on {router['host']}:{router['netconf_port']}...")

            with manager.connect(
                host=router["host"],
                port=router["netconf_port"],
                username=router["username"],
                password=router["password"],
                hostkey_verify=False,
                device_params={"name": "csr"},
                look_for_keys=False,
                allow_agent=False,
                timeout=10
            ) as m:
                self.log("NETCONF test successful.")
                self.log(f"NETCONF capabilities found: {len(list(m.server_capabilities))}")

        except Exception as error:
            self.log(f"NETCONF test failed: {error}")

    def test_restconf(self, router):
        try:
            self.log(f"Testing RESTCONF on {router['restconf_base_url']}...")

            url = f"{router['restconf_base_url']}/restconf/data/Cisco-IOS-XE-native:native"

            response = requests.get(
                url,
                auth=(router["username"], router["password"]),
                headers={"Accept": "application/yang-data+json"},
                verify=False,
                timeout=10
            )

            if response.status_code in [200, 201, 204]:
                self.log(f"RESTCONF test successful. Status: {response.status_code}")
            else:
                self.log(f"RESTCONF test failed. Status: {response.status_code}")
                self.log(f"Response body: {response.text[:300]}")

        except Exception as error:
            self.log(f"RESTCONF test failed: {error}")

    def get_device_info_threaded(self):
        threading.Thread(target=self.get_device_info, daemon=True).start()

    def get_device_info(self):
        try:
            self.set_buttons_state("disabled")
            router = self.get_router_settings()

            self.start_loading("Retrieving device info...")
            self.log("Retrieving device info via RESTCONF...")

            url = f"{router['restconf_base_url']}/restconf/data/Cisco-IOS-XE-native:native"

            response = requests.get(
                url,
                auth=(router["username"], router["password"]),
                headers={"Accept": "application/yang-data+json"},
                verify=False,
                timeout=30
            )

            self.check_response(response, "Retrieve device native data")

            data = response.json()
            native = data.get("Cisco-IOS-XE-native:native", {})
            hostname = native.get("hostname", "Unknown")

            self.log("Device Info:")
            self.log(f"Hostname: {hostname}")
            self.log("Model: retrieve via RESTCONF operational endpoint if available")
            self.log("Serial: retrieve via RESTCONF operational endpoint if available")
            self.log("IOS-XE version: retrieve via RESTCONF operational endpoint if available")
            self.log("Uptime: retrieve via RESTCONF operational endpoint if available")

            self.stop_loading("Device info retrieved.", 1)

        except Exception as error:
            self.stop_loading("Device info failed.", 0)
            self.log(f"Device info failed: {error}")
            messagebox.showerror("Device Info Failed", str(error))

        finally:
            self.set_buttons_state("normal")

    def get_running_config_restconf(self, router):
        url = f"{router['restconf_base_url']}/restconf/data/Cisco-IOS-XE-native:native"

        response = requests.get(
            url,
            auth=(router["username"], router["password"]),
            headers={"Accept": "application/yang-data+json"},
            verify=False,
            timeout=30
        )

        self.check_response(response, "Retrieve running config")

        try:
            return json.dumps(response.json(), indent=4)
        except Exception:
            return response.text

    def backup_running_config(self, router):
        os.makedirs(BACKUP_DIR, exist_ok=True)

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"backup_{router['host'].replace('.', '_')}_{timestamp}.json"
        path = os.path.join(BACKUP_DIR, filename)

        self.log("Creating running-config backup before deployment...")
        content = self.get_running_config_restconf(router)

        with open(path, "w", encoding="utf-8") as file:
            file.write(content)

        self.log(f"Backup saved: {path}")
        return path

    def diff_viewer_threaded(self):
        threading.Thread(target=self.diff_viewer, daemon=True).start()

    def get_normalized_running_config(self, router):
        data = json.loads(self.get_running_config_restconf(router))
        native = data.get("Cisco-IOS-XE-native:native", {})

        normalized = {
            "hostname": native.get("hostname", ""),
            "interfaces": [],
            "ospf": {
                "process_id": "",
                "router_id": "",
                "networks": []
            }
        }

        gig_interfaces = native.get("interface", {}).get("GigabitEthernet", [])

        for intf in gig_interfaces:
            ip_primary = (
                intf.get("ip", {})
                .get("address", {})
                .get("primary", {})
            )

            normalized["interfaces"].append({
                "name": f"GigabitEthernet{intf.get('name', '')}",
                "description": intf.get("description", ""),
                "ip": ip_primary.get("address", ""),
                "netmask": ip_primary.get("mask", "")
            })

        ospf_processes = (
            native.get("router", {})
            .get("Cisco-IOS-XE-ospf:router-ospf", {})
            .get("ospf", {})
            .get("process-id", [])
        )

        if ospf_processes:
            proc = ospf_processes[0]
            normalized["ospf"]["process_id"] = proc.get("id", "")
            normalized["ospf"]["router_id"] = proc.get("router-id", "")

            for net in proc.get("network", []):
                normalized["ospf"]["networks"].append({
                    "ip": net.get("ip", ""),
                    "mask": net.get("wildcard", ""),
                    "area": net.get("area", 0)
                })

        return json.dumps(normalized, indent=4)

    def diff_viewer(self):
        try:
            self.set_buttons_state("disabled")
            router = self.get_router_settings()
            config = self.get_selected_config()

            self.start_loading("Generating diff viewer...")
            self.log("Generating diff viewer...")

            new_config = self.download_selected_config(config)

            if config["type"] == "NETCONF":
                diff_text = (
                    "Diff Viewer notice:\n\n"
                    "The current running configuration is retrieved through RESTCONF as JSON,\n"
                    "while the selected configuration is a NETCONF XML file.\n\n"
                    "A direct line-by-line diff between JSON and XML is not useful.\n\n"
                    "Selected NETCONF XML config:\n\n"
                    f"{new_config}"
                )

                self.root.after(0, lambda: self.show_diff_window(diff_text))
                self.stop_loading("NETCONF XML preview loaded in Diff Viewer.", 1)
                return

            current_config = self.get_normalized_running_config(router)
            new_config = self.format_preview_content(new_config, "RESTCONF")

            diff = difflib.unified_diff(
                current_config.splitlines(),
                new_config.splitlines(),
                fromfile="Current normalized config",
                tofile=f"New config: {config['name']}",
                lineterm=""
            )

            diff_text = "\n".join(diff)

            if not diff_text.strip():
                diff_text = "No differences found."

            self.root.after(0, lambda: self.show_diff_window(diff_text))
            self.stop_loading("Diff generated.", 1)

        except Exception as error:
            self.stop_loading("Diff failed.", 0)
            self.log(f"Diff failed: {error}")
            messagebox.showerror("Diff Failed", str(error))

        finally:
            self.root.after(0, lambda: self.set_buttons_state("normal"))

    def show_diff_window(self, diff_text):
        window = ctk.CTkToplevel(self.root)

        window.transient(self.root)
        window.lift()
        window.focus_force()
        window.attributes("-topmost", True)
        window.after(300, lambda: window.attributes("-topmost", False))

        window.title("Diff Viewer")
        window.geometry("1050x750")
        window.minsize(850, 550)

        ctk.CTkLabel(
            window,
            text="Diff Viewer - Current Config vs New Config",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        textbox = ctk.CTkTextbox(
            window,
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=10
        )
        textbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        textbox.insert("1.0", diff_text)
        textbox.configure(state="disabled")

    def push_config_threaded(self):
        threading.Thread(target=self.push_config, daemon=True).start()

    def confirm_push(self, config, router):
        message = (
            "You are about to deploy a configuration.\n\n"
            f"Config: {config['name']}\n"
            f"Detected protocol: {config['type']}\n"
            f"Target host: {router['host']}\n"
        )

        if config["type"] == "NETCONF":
            message += f"Target port: {router['netconf_port']}\n"
        else:
            message += f"Target port: {router['restconf_port']}\n"

        if self.backup_before_deploy_var.get():
            message += "\nBackup before deploy: enabled\n"
        else:
            message += "\nBackup before deploy: disabled\n"

        message += "\nAre you sure you want to continue?"
        return messagebox.askyesno("Confirm Deployment", message)

    def push_config(self):
        try:
            self.set_buttons_state("disabled")
            config = self.get_selected_config()
            router = self.get_router_settings()

            if not self.confirm_push(config, router):
                self.log("Deployment cancelled by user.")
                self.stop_loading("Deployment cancelled.", 0)
                return

            self.start_loading(f"{config['type']} detected - deploying {config['name']}...")
            self.log(f"{config['type']} detected based on file extension.")
            self.log(f"Target router: {router['host']}")

            if self.backup_before_deploy_var.get():
                self.backup_running_config(router)

            config_content = self.download_selected_config(config)

            if config["type"] == "NETCONF":
                self.deploy_netconf(config_content, router)
            elif config["type"] == "RESTCONF":
                self.deploy_restconf(config_content, router)
            else:
                raise ValueError("Unsupported config type.")

            self.stop_loading("Deployment completed successfully.", 1)
            self.log("Deployment completed successfully.")

        except Exception as error:
            self.stop_loading("Deployment failed.", 0)
            self.log(f"Deployment failed: {error}")
            messagebox.showerror("Deployment failed", str(error))

        finally:
            self.set_buttons_state("normal")

    def deploy_netconf(self, config_xml, router):
        if not config_xml.startswith("<config"):
            raise ValueError("Selected XML file is not a valid NETCONF <config> file.")

        self.log(f"Connecting via NETCONF to {router['host']}:{router['netconf_port']}...")
        self.set_status("Connecting via NETCONF...", 0.35)

        with manager.connect(
            host=router["host"],
            port=router["netconf_port"],
            username=router["username"],
            password=router["password"],
            hostkey_verify=False,
            device_params={"name": "csr"},
            look_for_keys=False,
            allow_agent=False,
            timeout=30
        ) as m:
            caps = list(m.server_capabilities)

            if not any("candidate" in cap for cap in caps):
                raise RuntimeError("Candidate datastore is not supported on this device.")

            self.log("Locking candidate datastore...")
            self.set_status("Locking candidate datastore...", 0.45)
            m.lock(target="candidate")

            try:
                self.log("Loading config into candidate...")
                self.set_status("Loading config into candidate...", 0.60)
                m.edit_config(
                    target="candidate",
                    config=config_xml,
                    error_option="stop-on-error"
                )

                self.log("Validating candidate configuration...")
                self.set_status("Validating candidate configuration...", 0.75)
                m.validate(source="candidate")

                self.log("Committing candidate to running...")
                self.set_status("Committing candidate to running...", 0.90)
                m.commit()

                self.log("NETCONF deployment successful.")

            except RPCError as err:
                self.log(f"NETCONF RPCError: {err}")
                self.log("Discarding candidate changes...")
                m.discard_changes()
                raise

            except Exception as err:
                self.log(f"NETCONF deployment error: {err}")
                self.log("Discarding candidate changes...")
                m.discard_changes()
                raise

            finally:
                self.log("Unlocking candidate datastore...")
                m.unlock(target="candidate")

    def deploy_restconf(self, config_json_text, router):
        self.log("Parsing JSON config...")
        self.set_status("Parsing JSON config...", 0.35)

        config = json.loads(config_json_text)

        self.patch_hostname(config["hostname"], router)

        for interface in config["interfaces"]:
            self.put_interface(interface, router)

        self.delete_ospf(config["ospf"], router)
        self.post_ospf_process(config["ospf"], router)
        self.verify_running_config(router)

        self.log("RESTCONF deployment successful.")

    def check_response(self, resp, action):
        if resp.status_code in [200, 201, 204]:
            self.log(f"{action} successful. Status: {resp.status_code}")
            return

        self.log(f"{action} failed. Status: {resp.status_code}")
        self.log(f"Response body: {resp.text}")
        resp.raise_for_status()

    def patch_hostname(self, hostname, router):
        self.set_status(f"Configuring hostname {hostname}...", 0.45)

        url = f"{router['restconf_base_url']}/restconf/data/Cisco-IOS-XE-native:native"

        payload = {
            "Cisco-IOS-XE-native:native": {
                "hostname": hostname
            }
        }

        resp = requests.patch(
            url,
            auth=(router["username"], router["password"]),
            headers=RESTCONF_HEADERS,
            json=payload,
            verify=False,
            timeout=30
        )

        self.check_response(resp, f"Configure hostname {hostname}")

    def put_interface(self, interface, router):
        self.set_status(f"Configuring interface {interface['name']}...", 0.60)

        encoded_name = quote(interface["name"], safe="")
        url = f"{router['restconf_base_url']}/restconf/data/ietf-interfaces:interfaces/interface={encoded_name}"

        payload = {
            "ietf-interfaces:interface": {
                "name": interface["name"],
                "description": interface["description"],
                "type": "iana-if-type:ethernetCsmacd",
                "enabled": True,
                "ietf-ip:ipv4": {
                    "address": [
                        {
                            "ip": interface["ip"],
                            "netmask": interface["netmask"]
                        }
                    ]
                }
            }
        }

        resp = requests.put(
            url,
            auth=(router["username"], router["password"]),
            headers=RESTCONF_HEADERS,
            json=payload,
            verify=False,
            timeout=30
        )

        self.check_response(resp, f"Configure interface {interface['name']}")

    def delete_ospf(self, ospf, router):
        self.set_status(f"Deleting old OSPF process {ospf['process_id']}...", 0.75)

        url = (
            f"{router['restconf_base_url']}/restconf/data/"
            f"Cisco-IOS-XE-native:native/router/"
            f"Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={ospf['process_id']}"
        )

        resp = requests.delete(
            url,
            auth=(router["username"], router["password"]),
            headers=RESTCONF_HEADERS,
            verify=False,
            timeout=30
        )

        if resp.status_code == 404:
            self.log(f"No existing OSPF process {ospf['process_id']} found, skipping delete.")
            return

        self.check_response(resp, f"Delete OSPF process {ospf['process_id']}")

    def post_ospf_process(self, ospf, router):
        self.set_status(f"Configuring OSPF process {ospf['process_id']}...", 0.85)

        url = f"{router['restconf_base_url']}/restconf/data/Cisco-IOS-XE-native:native/router"

        payload = {
            "Cisco-IOS-XE-native:router": {
                "Cisco-IOS-XE-ospf:router-ospf": {
                    "ospf": {
                        "process-id": [
                            {
                                "id": ospf["process_id"],
                                "router-id": ospf["router_id"],
                                "network": [
                                    {
                                        "ip": net["ip"],
                                        "wildcard": net["mask"],
                                        "area": net["area"]
                                    }
                                    for net in ospf["networks"]
                                ]
                            }
                        ]
                    }
                }
            }
        }

        resp = requests.patch(
            url,
            auth=(router["username"], router["password"]),
            headers=RESTCONF_HEADERS,
            json=payload,
            verify=False,
            timeout=30
        )

        self.check_response(resp, f"Configure OSPF process {ospf['process_id']}")

    def verify_running_config(self, router):
        self.set_status("Verifying running config...", 0.95)

        url = f"{router['restconf_base_url']}/restconf/data/Cisco-IOS-XE-native:native"

        resp = requests.get(
            url,
            auth=(router["username"], router["password"]),
            headers={"Accept": "application/yang-data+json"},
            verify=False,
            timeout=30
        )

        self.check_response(resp, "Retrieve running config")

    def export_log(self):
        content = self.log_box.get("1.0", "end").strip()

        if not content:
            messagebox.showinfo("Export Log", "There is no log content to export.")
            return

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        default_name = f"deployment_log_{timestamp}.txt"

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if not path:
            return

        with open(path, "w", encoding="utf-8") as file:
            file.write(content)

        self.log(f"Log exported to: {path}")
        messagebox.showinfo("Export Log", "Log exported successfully.")

    # =========================
    # KVM Router VM Deployment
    # =========================

    def open_vm_deployer_window(self):
        window = ctk.CTkToplevel(self.root)
        window.title("Deploy Router VM")
        window.geometry("700x660")
        window.minsize(650, 560)

        window.transient(self.root)
        window.lift()
        window.focus_force()
        window.attributes("-topmost", True)
        window.after(300, lambda: window.attributes("-topmost", False))

        frame = ctk.CTkFrame(window, corner_radius=14)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            frame,
            text="Deploy Cisco Router VM",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        def add_labeled_entry(parent, label_text, placeholder_text="", show=None, default_value=""):
            ctk.CTkLabel(
                parent,
                text=label_text,
                font=ctk.CTkFont(size=12),
                text_color="gray75"
            ).pack(anchor="w", padx=15, pady=(8, 2))

            entry = ctk.CTkEntry(
                parent,
                placeholder_text=placeholder_text,
                show=show
            )
            entry.pack(fill="x", padx=15, pady=(0, 4))

            if default_value:
                entry.insert(0, default_value)

            return entry

        self.kvm_host_entry = add_labeled_entry(
            frame,
            "KVM Host / IP",
            "Enter KVM hostname or IP",
            default_value="PLEX-Server"
        )

        self.kvm_user_entry = add_labeled_entry(
            frame,
            "SSH Username",
            "Enter SSH username",
            default_value="bjorn"
        )

        self.kvm_password_entry = add_labeled_entry(
            frame,
            "SSH Password",
            "Enter SSH password",
            show="*"
        )

        self.base_vm_entry = add_labeled_entry(
            frame,
            "Base VM Name",
            "Enter base VM name",
            default_value="CRS1000"
        )

        self.new_vm_entry = add_labeled_entry(
            frame,
            "New VM Name",
            "Enter new VM name",
            default_value="CSR-AUTO-01"
        )

        self.source_qcow_entry = add_labeled_entry(
            frame,
            "Source QCOW2 Path",
            "Enter source QCOW2 path",
            default_value="/mnt/RAID5/Virtual Machines/csr1000vng-universalk9.17.03.05-serial/virtioa_deploy.qcow2"
        )

        self.libvirt_network_entry = add_labeled_entry(
            frame,
            "Libvirt DHCP Network",
            "Enter libvirt network name",
            default_value="br0"
        )

        ctk.CTkButton(
            frame,
            text="🚀 Deploy VM",
            command=lambda: self.deploy_router_vm_threaded(window),
            height=40,
            fg_color="#15803D",
            hover_color="#166534"
        ).pack(anchor="w", padx=15, pady=(18, 10))

    def deploy_router_vm_threaded(self, window):
        threading.Thread(target=lambda: self.deploy_router_vm(window), daemon=True).start()

    def ssh_exec(self, ssh, command):
        stdin, stdout, stderr = ssh.exec_command(command)
        out = stdout.read().decode(errors="ignore")
        err = stderr.read().decode(errors="ignore")
        code = stdout.channel.recv_exit_status()

        if code != 0:
            raise RuntimeError(f"Command failed:\n{command}\n\n{err}")

        return out.strip()

    def generate_mac(self):
        return "52:54:00:%02x:%02x:%02x" % (
            random.randint(0x00, 0xFF),
            random.randint(0x00, 0xFF),
            random.randint(0x00, 0xFF)
        )

    def deploy_router_vm(self, window):
        ssh = None

        try:
            self.set_buttons_state("disabled")
            self.start_loading("Deploying router VM...")

            kvm_host = self.kvm_host_entry.get().strip()
            kvm_user = self.kvm_user_entry.get().strip()
            kvm_password = self.kvm_password_entry.get()
            base_vm = self.base_vm_entry.get().strip()
            new_vm = self.new_vm_entry.get().strip()
            source_qcow = self.source_qcow_entry.get().strip()
            libvirt_network = self.libvirt_network_entry.get().strip()

            if not all([kvm_host, kvm_user, kvm_password, base_vm, new_vm, source_qcow, libvirt_network]):
                raise ValueError("All VM deployment fields are required.")

            self.log(f"Connecting to KVM host {kvm_host}...")

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=kvm_host,
                username=kvm_user,
                password=kvm_password,
                timeout=15
            )

            self.log(f"Reading XML from base VM: {base_vm}")
            base_xml = self.ssh_exec(ssh, f"sudo virsh dumpxml {base_vm}")

            source_dir = os.path.dirname(source_qcow)
            new_disk = f"{source_dir}/{new_vm}.qcow2"
            remote_xml = f"/tmp/{new_vm}.xml"

            self.log(f"Cloning disk to {new_disk}...")
            self.ssh_exec(ssh, f"sudo cp '{source_qcow}' '{new_disk}'")
            self.ssh_exec(ssh, f"sudo chown libvirt-qemu:libvirt-qemu '{new_disk}' || true")

            root = ET.fromstring(base_xml)

            name_node = root.find("name")
            if name_node is not None:
                name_node.text = new_vm

            uuid_node = root.find("uuid")
            if uuid_node is not None:
                uuid_node.text = str(uuid.uuid4())

            disk_source = root.find(".//devices/disk/source")
            if disk_source is not None:
                disk_source.set("file", new_disk)

            interfaces = root.findall(".//devices/interface")
            management_mac = None

            for index, intf in enumerate(interfaces):
                mac_node = intf.find("mac")
                if mac_node is not None:
                    new_mac = self.generate_mac()
                    mac_node.set("address", new_mac)

                    if index == 0:
                        management_mac = new_mac

                if index == 0:
                    intf.set("type", "network")

                    source_node = intf.find("source")
                    if source_node is None:
                        source_node = ET.SubElement(intf, "source")

                    source_node.attrib.clear()
                    source_node.set("network", libvirt_network)

            new_xml = ET.tostring(root, encoding="unicode")

            self.log(f"Uploading generated XML to {remote_xml}...")
            self.ssh_exec(ssh, f"cat > '{remote_xml}' << 'EOF'\n{new_xml}\nEOF")

            self.log(f"Defining VM {new_vm}...")
            self.ssh_exec(ssh, f"sudo virsh define '{remote_xml}'")

            self.log(f"Starting VM {new_vm}...")
            self.ssh_exec(ssh, f"sudo virsh start {new_vm}")

            found_ip = ""

            if management_mac:
                self.log(f"Waiting for DHCP lease for Gi1 MAC {management_mac}...")

                max_attempts = 60

                for attempt in range(max_attempts):
                    progress_msg = f"Checking DHCP/ARP... ({attempt + 1}/{max_attempts})"

                    self.set_status(progress_msg, 0.95)

                    if attempt == 0:
                        self.log(progress_msg)
                    else:
                        self.update_last_log_line(progress_msg)

                    found_ip = ""

                    # 1. Check libvirt DHCP leases
                    leases = self.ssh_exec(
                        ssh,
                        f"sudo virsh net-dhcp-leases {libvirt_network} || true"
                    )

                    for line in leases.splitlines():
                        if management_mac.lower() in line.lower():
                            parts = line.split()

                            for part in parts:
                                if "/" in part and "." in part:
                                    found_ip = part.split("/")[0]
                                    break

                    # 2. Check ARP cache
                    if not found_ip:
                        arp_output = self.ssh_exec(
                            ssh,
                            f"ip neigh | grep -i '{management_mac}' || true"
                        )

                        for line in arp_output.splitlines():
                            parts = line.split()

                            if parts and "." in parts[0]:
                                found_ip = parts[0]
                                break

                    # 3. Every 10 attempts: ping sweep subnet to populate ARP cache
                    if not found_ip and attempt % 10 == 0:
                        self.log("No ARP entry yet, scanning local subnet...")

                        scan_cmd = (
                            "IP=$(ip -4 -o addr show br0 | awk '{print $4}' | cut -d/ -f1 | head -1); "
                            "PREFIX=${IP%.*}; "
                            "for i in $(seq 1 254); do ping -c1 -W1 ${PREFIX}.${i} >/dev/null 2>&1 & done; "
                            "wait; "
                            f"ip neigh | grep -i '{management_mac}' || true"
                        )

                        arp_output = self.ssh_exec(ssh, scan_cmd)

                        for line in arp_output.splitlines():
                            parts = line.split()

                            if parts and "." in parts[0]:
                                found_ip = parts[0]
                                break

                    if found_ip:
                        self.update_last_log_line(
                            f"Management IP found for Gi1: {found_ip}"
                        )
                        self.log(f"DHCP IP found: {found_ip}")
                        break

                    time.sleep(2)
                    
                    
            if found_ip:
                self.log(f"DHCP IP found: {found_ip}")
                self.root.after(0, lambda: self.host_entry.delete(0, "end"))
                self.root.after(0, lambda: self.host_entry.insert(0, found_ip))

                messagebox.showinfo(
                    "VM Deployed",
                    f"VM {new_vm} deployed successfully.\n\nIP address: {found_ip}"
                )
            else:
                self.log("VM deployed, but no DHCP lease found yet.")
                messagebox.showinfo(
                    "VM Deployed",
                    f"VM {new_vm} deployed successfully.\n\nNo DHCP lease found yet."
                )

            self.stop_loading("Router VM deployed.", 1)
            self.root.after(0, window.destroy)

        except Exception as error:
            self.stop_loading("VM deployment failed.", 0)
            self.log(f"VM deployment failed: {error}")
            messagebox.showerror("VM Deployment Failed", str(error))

        finally:
            if ssh:
                ssh.close()

            self.set_buttons_state("normal")


def main():
    root = ctk.CTk()
    ModernConfigPushGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
