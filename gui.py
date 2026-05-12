import difflib
import json
import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import requests

from constants import LOCAL_CONFIG_DIR
from utils.profiles import load_profiles_from_file, save_profiles_to_file
from utils.config_loader import load_local_configs, read_config_file
from utils.network import ping_host

from services.github_service import sync_configs_from_github
from services.backup_service import backup_running_config
from services.netconf_service import deploy_netconf, get_running_config_netconf, test_netconf
from services.restconf_service import deploy_restconf, get_running_config_restconf, test_restconf
from services.ssh_service import deploy_ssh_cli
from services.vm_service import deploy_router_vm


class ModernConfigPushGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Cisco Config Deployer - M1jsXploit")
        self.root.geometry("1260x952")
        self.root.minsize(1000, 760)

        self.configs = []
        self.is_loading = False
        self.password_visible = False
        self.profiles = load_profiles_from_file()

        os.makedirs(LOCAL_CONFIG_DIR, exist_ok=True)

        self.create_widgets()
        self.load_profile_dropdown()
        self.reload_local_configs()

    def create_widgets(self):
        self.main_frame = ctk.CTkFrame(self.root, corner_radius=16)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=8)

        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=22, pady=(14, 6))

        ctk.CTkLabel(
            header_frame,
            text="Cisco Config Deployer",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            header_frame,
            text="Deploy NETCONF XML, RESTCONF JSON and SSH CLI configs",
            font=ctk.CTkFont(size=13),
            text_color="gray70"
        ).pack(anchor="w", pady=(3, 0))

        settings_frame = ctk.CTkFrame(self.main_frame, corner_radius=14, fg_color="#323232")
        settings_frame.pack(fill="x", padx=22, pady=(8, 8))

        ctk.CTkLabel(
            settings_frame,
            text="Profiles & Target",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=18, pady=(12, 6))

        profile_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        profile_row.pack(fill="x", padx=18, pady=(0, 8))

        self.profile_name_entry = ctk.CTkEntry(profile_row, placeholder_text="Profile name")
        self.profile_name_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.profile_var = tk.StringVar(value="No profiles")
        self.profile_dropdown = ctk.CTkOptionMenu(
            profile_row,
            variable=self.profile_var,
            values=["No profiles"],
            width=200
        )
        self.profile_dropdown.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            profile_row,
            text="📂 Load Profile",
            command=self.load_selected_profile,
            height=34,
            fg_color="#0891B2",
            hover_color="#0E7490"
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            profile_row,
            text="💾 Save Profile",
            command=self.save_current_profile,
            height=34,
            fg_color="#7C3AED",
            hover_color="#6D28D9"
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            profile_row,
            text="🔌 Test",
            command=self.test_connection_threaded,
            height=34,
            fg_color="#2563EB",
            hover_color="#1D4ED8"
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            profile_row,
            text="ℹ️ Info",
            command=self.get_device_info_threaded,
            height=34,
            fg_color="#0F766E",
            hover_color="#115E59"
        ).pack(side="left")

        target_grid = ctk.CTkFrame(settings_frame, fg_color="transparent")
        target_grid.pack(fill="x", padx=18, pady=(0, 12))

        labels = ["Host / IP", "Username", "Password", "NETCONF Port", "RESTCONF Port"]

        for i, text in enumerate(labels):
            ctk.CTkLabel(
                target_grid,
                text=text,
                font=ctk.CTkFont(size=11),
                text_color="gray75"
            ).grid(row=0, column=i, sticky="w", padx=6, pady=(0, 3))

        self.host_entry = ctk.CTkEntry(target_grid, placeholder_text="10.10.10.10")
        self.host_entry.grid(row=1, column=0, padx=6, pady=(0, 6), sticky="ew")

        self.username_entry = ctk.CTkEntry(target_grid, placeholder_text="bjorn")
        self.username_entry.grid(row=1, column=1, padx=6, pady=(0, 6), sticky="ew")

        password_frame = ctk.CTkFrame(target_grid, fg_color="transparent")
        password_frame.grid(row=1, column=2, padx=6, pady=(0, 6), sticky="ew")
        password_frame.columnconfigure(0, weight=1)

        self.password_entry = ctk.CTkEntry(password_frame, placeholder_text="password", show="*")
        self.password_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.password_toggle_button = ctk.CTkButton(
            password_frame,
            text="👁",
            width=38,
            command=self.toggle_password_visibility,
            fg_color="#444444",
            hover_color="#555555"
        )
        self.password_toggle_button.grid(row=0, column=1)

        self.netconf_port_entry = ctk.CTkEntry(target_grid, placeholder_text="830")
        self.netconf_port_entry.grid(row=1, column=3, padx=6, pady=(0, 6), sticky="ew")

        self.restconf_port_entry = ctk.CTkEntry(target_grid, placeholder_text="443")
        self.restconf_port_entry.grid(row=1, column=4, padx=6, pady=(0, 6), sticky="ew")

        for col in range(5):
            target_grid.columnconfigure(col, weight=1)

        select_frame = ctk.CTkFrame(self.main_frame, corner_radius=14)
        select_frame.pack(fill="x", padx=22, pady=(0, 8))

        select_row = ctk.CTkFrame(select_frame, fg_color="transparent")
        select_row.pack(fill="x", padx=18, pady=12)

        ctk.CTkLabel(
            select_row,
            text="Config:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=(0, 10))

        self.config_var = tk.StringVar()
        self.config_dropdown = ctk.CTkOptionMenu(
            select_row,
            variable=self.config_var,
            values=["Loading configs..."],
            width=500
        )
        self.config_dropdown.pack(side="left", padx=(0, 10))

        self.refresh_button = ctk.CTkButton(select_row, text="🔄 Refresh", command=self.load_configs_threaded, height=34)
        self.refresh_button.pack(side="left", padx=(0, 8))

        self.preview_button = ctk.CTkButton(select_row, text="👁 Preview", command=self.preview_config_threaded, height=34)
        self.preview_button.pack(side="left", padx=(0, 8))

        self.diff_button = ctk.CTkButton(select_row, text="🔍 Diff", command=self.diff_viewer_threaded, height=34)
        self.diff_button.pack(side="left", padx=(0, 8))

        self.push_button = ctk.CTkButton(
            select_row,
            text="🚀 Push Config",
            command=self.push_config_threaded,
            height=34,
            fg_color="#15803D",
            hover_color="#166534"
        )
        self.push_button.pack(side="left")

        actions_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        actions_frame.pack(fill="x", padx=22, pady=(0, 8))

        self.backup_before_deploy_var = tk.BooleanVar(value=True)
        self.backup_checkbox = ctk.CTkCheckBox(
            actions_frame,
            text="Backup running-config before deploy",
            variable=self.backup_before_deploy_var
        )
        self.backup_checkbox.pack(side="left", padx=(0, 14))

        self.export_log_button = ctk.CTkButton(actions_frame, text="📄 Export Log", command=self.export_log, height=34)
        self.export_log_button.pack(side="left", padx=(0, 8))

        self.clear_button = ctk.CTkButton(actions_frame, text="🗑 Clear Log", command=self.clear_log, height=34)
        self.clear_button.pack(side="left", padx=(0, 8))

        self.deploy_vm_button = ctk.CTkButton(
            actions_frame,
            text="🖥 Deploy Router VM",
            command=self.open_vm_deployer_window,
            height=34,
            fg_color="#9333EA",
            hover_color="#7E22CE"
        )
        self.deploy_vm_button.pack(side="left")

        progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        progress_frame.pack(fill="x", padx=22, pady=(0, 6))

        self.status_label = ctk.CTkLabel(progress_frame, text="Ready", text_color="gray70")
        self.status_label.pack(anchor="w")

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", pady=(4, 0))
        self.progress_bar.set(0)

        log_frame = ctk.CTkFrame(self.main_frame, corner_radius=14)
        log_frame.pack(fill="both", expand=True, padx=22, pady=(0, 8))

        ctk.CTkLabel(
            log_frame,
            text="Deployment Log",
            font=ctk.CTkFont(size=17, weight="bold")
        ).pack(anchor="w", padx=18, pady=(12, 6))

        self.log_box = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=13),
            corner_radius=10
        )
        self.log_box.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        footer = ctk.CTkLabel(
            self.main_frame,
            text="Cisco Config Deployer v1.0 | by M1jsXploit",
            font=ctk.CTkFont(size=11),
            text_color="gray55"
        )
        footer.pack(anchor="e", padx=22, pady=(0, 8))

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
        for button in [
            self.refresh_button,
            self.preview_button,
            self.diff_button,
            self.push_button,
            self.export_log_button,
            self.clear_button,
            self.deploy_vm_button,
        ]:
            button.configure(state=state)

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

    def toggle_password_visibility(self):
        self.password_visible = not self.password_visible

        if self.password_visible:
            self.password_entry.configure(show="")
            self.password_toggle_button.configure(text="🙈")
        else:
            self.password_entry.configure(show="*")
            self.password_toggle_button.configure(text="👁")

    def get_router_settings(self):
        host = self.host_entry.get().strip()
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        netconf_port = self.netconf_port_entry.get().strip() or "830"
        restconf_port = self.restconf_port_entry.get().strip() or "443"

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
            "restconf_base_url": f"https://{host}:{restconf_port}",
        }

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
            "restconf_port": self.restconf_port_entry.get().strip(),
        }

        save_profiles_to_file(self.profiles)
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

        self.netconf_port_entry.delete(0, "end")
        self.netconf_port_entry.insert(0, profile.get("netconf_port", "830"))

        self.restconf_port_entry.delete(0, "end")
        self.restconf_port_entry.insert(0, profile.get("restconf_port", "443"))

        self.password_entry.configure(show="*")
        self.password_visible = False
        self.password_toggle_button.configure(text="👁")

        self.log(f"Profile loaded with password: {name}")

    def reload_local_configs(self):
        self.configs = load_local_configs()

        if not self.configs:
            self.config_dropdown.configure(values=["No local configs found"])
            self.config_var.set("No local configs found")
            self.log("No local configs found.")
            return

        values = [f"{cfg['name']} ({cfg['type']})" for cfg in self.configs]
        self.config_dropdown.configure(values=values)
        self.config_var.set(values[0])
        self.log(f"Loaded {len(self.configs)} local config(s).")

    def get_selected_config(self):
        selected_name = self.config_var.get()

        for config in self.configs:
            if f"{config['name']} ({config['type']})" == selected_name:
                return config

        raise ValueError("No valid config selected.")

    def load_configs_threaded(self):
        threading.Thread(target=self.load_configs, daemon=True).start()

    def load_configs(self):
        try:
            self.set_buttons_state("disabled")
            self.start_loading("Syncing configs from GitHub...")

            sync_configs_from_github(self.log)
            self.reload_local_configs()

            self.stop_loading("Configs refreshed.", 1)

        except Exception as error:
            self.stop_loading("Refresh failed.", 0)
            self.log(f"GitHub sync failed: {error}")
            messagebox.showerror("GitHub Error", str(error))

        finally:
            self.set_buttons_state("normal")

    def preview_config_threaded(self):
        threading.Thread(target=self.preview_config, daemon=True).start()

    def preview_config(self):
        try:
            self.set_buttons_state("disabled")
            config = self.get_selected_config()

            self.start_loading(f"{config['type']} detected - previewing {config['name']}...")
            self.log(f"{config['type']} detected based on file extension.")

            content = read_config_file(config)

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
        preview.title(f"Preview - {filename}")
        preview.geometry("950x700")
        preview.transient(self.root)
        preview.lift()
        preview.focus_force()

        ctk.CTkLabel(
            preview,
            text=f"Preview: {filename} ({config_type})",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        textbox = ctk.CTkTextbox(preview, font=ctk.CTkFont(family="Consolas", size=12))
        textbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        pretty_content = self.format_preview_content(content, config_type)
        textbox.insert("1.0", pretty_content)
        textbox.configure(state="disabled")

    def format_preview_content(self, content, config_type):
        if config_type == "RESTCONF":
            try:
                return json.dumps(json.loads(content), indent=4)
            except Exception:
                return content
        return content

    def test_connection_threaded(self):
        threading.Thread(target=self.test_connection, daemon=True).start()

    def test_connection(self):
        try:
            self.set_buttons_state("disabled")
            router = self.get_router_settings()

            self.start_loading("Testing connection...")
            self.log(f"Testing connection to {router['host']}...")

            ping_ok = ping_host(router["host"])
            self.log(f"Ping test: {'successful' if ping_ok else 'failed'}")

            test_netconf(router, self.log)
            test_restconf(router, self.log)

            self.stop_loading("Connection test completed.", 1)

        except Exception as error:
            self.stop_loading("Connection test failed.", 0)
            self.log(f"Connection test failed: {error}")
            messagebox.showerror("Connection Test Failed", str(error))

        finally:
            self.set_buttons_state("normal")

    def get_device_info_threaded(self):
        threading.Thread(target=self.get_device_info, daemon=True).start()

    def get_device_info(self):
        try:
            self.set_buttons_state("disabled")
            router = self.get_router_settings()

            self.start_loading("Retrieving device info...")
            self.log("Retrieving device info via NETCONF...")

            content = get_running_config_netconf(router)

            hostname = "Unknown"
            if "<hostname>" in content:
                hostname = content.split("<hostname>")[1].split("</hostname>")[0]

            self.log("Device Info:")
            self.log(f"Hostname: {hostname}")
            self.log("Running config retrieved via NETCONF.")

            self.stop_loading("Device info retrieved.", 1)

        except Exception as error:
            self.stop_loading("Device info failed.", 0)
            self.log(f"Device info failed: {error}")
            messagebox.showerror("Device Info Failed", str(error))

        finally:
            self.set_buttons_state("normal")

    def diff_viewer_threaded(self):
        threading.Thread(target=self.diff_viewer, daemon=True).start()

    def diff_viewer(self):
        try:
            self.set_buttons_state("disabled")
            router = self.get_router_settings()
            config = self.get_selected_config()

            self.start_loading("Generating diff viewer...")
            self.log("Generating diff viewer...")

            new_config = read_config_file(config)

            if config["type"] == "NETCONF":
                current_config = get_running_config_netconf(router)
            elif config["type"] == "RESTCONF":
                current_config = get_running_config_restconf(router, self.log)
            else:
                current_config = "SSH CLI diff uses current file only. Running CLI config not fetched."

            diff = difflib.unified_diff(
                current_config.splitlines(),
                new_config.splitlines(),
                fromfile="Current config",
                tofile=f"New config: {config['name']}",
                lineterm=""
            )

            diff_text = "\n".join(diff) or "No differences found."

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
        window.title("Diff Viewer")
        window.geometry("1050x750")
        window.transient(self.root)
        window.lift()
        window.focus_force()

        ctk.CTkLabel(
            window,
            text="Diff Viewer - Current Config vs New Config",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        textbox = ctk.CTkTextbox(window, font=ctk.CTkFont(family="Consolas", size=12))
        textbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        textbox.insert("1.0", diff_text)
        textbox.configure(state="disabled")

    def confirm_push(self, config, router):
        port = router["netconf_port"] if config["type"] == "NETCONF" else router["restconf_port"]

        message = (
            "You are about to deploy a configuration.\n\n"
            f"Config: {config['name']}\n"
            f"Detected protocol: {config['type']}\n"
            f"Target host: {router['host']}\n"
            f"Target port: {port}\n"
        )

        message += "\nBackup before deploy: enabled\n" if self.backup_before_deploy_var.get() else "\nBackup before deploy: disabled\n"
        message += "\nAre you sure you want to continue?"

        return messagebox.askyesno("Confirm Deployment", message)

    def push_config_threaded(self):
        threading.Thread(target=self.push_config, daemon=True).start()

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
                backup_running_config(router, config["type"], self.log)

            config_content = read_config_file(config)

            if config["type"] == "NETCONF":
                deploy_netconf(config_content, router, self.log, self.set_status)
            elif config["type"] == "RESTCONF":
                deploy_restconf(config_content, router, self.log, self.set_status)
            elif config["type"] == "SSH":
                deploy_ssh_cli(config_content, router, self.log, self.set_status)
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

    def open_vm_deployer_window(self):
        messagebox.showinfo(
            "VM Deployment",
            "VM deployment service is split into services/vm_service.py.\n"
            "The GUI window can be re-added here when needed."
        )