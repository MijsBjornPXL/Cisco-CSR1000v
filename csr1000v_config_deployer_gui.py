import json
import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, filedialog
from urllib.parse import quote

import customtkinter as ctk
import requests
from ncclient import manager
from ncclient.operations import RPCError

requests.packages.urllib3.disable_warnings()

GITHUB_API_URL = "https://api.github.com/repos/MijsBjornPXL/Cisco-CSR1000v/contents/Configs?ref=main"
PROFILE_FILE = "csr1000v_profiles.json"

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
        self.root.geometry("1120x900")
        self.root.minsize(950, 700)

        self.configs = []
        self.is_loading = False
        self.profiles = self.load_profiles_from_file()

        self.create_widgets()
        self.load_profile_dropdown()
        self.load_configs_threaded()

    def create_widgets(self):
        self.main_frame = ctk.CTkFrame(self.root, corner_radius=16)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header_frame,
            text="Cisco Config Deployer",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            header_frame,
            text="Deploy NETCONF XML and RESTCONF JSON configs directly from GitHub",
            font=ctk.CTkFont(size=14),
            text_color="gray70"
        ).pack(anchor="w", pady=(5, 0))

        # =====================================
        # Unified Settings Card
        # =====================================

        settings_frame = ctk.CTkFrame(
            self.main_frame,
            corner_radius=14,
            fg_color="#323232"
        )
        settings_frame.pack(fill="x", padx=20, pady=(10, 15))

        # -------------------------
        # Profiles
        # -------------------------

        ctk.CTkLabel(
            settings_frame,
            text="Profiles",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 8))

        profile_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        profile_row.pack(fill="x", padx=15, pady=(0, 18))

        self.profile_name_entry = ctk.CTkEntry(
            profile_row,
            placeholder_text="Profile name"
        )
        self.profile_name_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.profile_var = tk.StringVar(value="No profiles")

        self.profile_dropdown = ctk.CTkOptionMenu(
            profile_row,
            variable=self.profile_var,
            values=["No profiles"],
            width=220
        )
        self.profile_dropdown.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            profile_row,
            text="Save Profile",
            command=self.save_current_profile,
            height=36,
            fg_color="#7C3AED",
            hover_color="#6D28D9"
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            profile_row,
            text="Load Profile",
            command=self.load_selected_profile,
            height=36,
            fg_color="#0891B2",
            hover_color="#0E7490"
        ).pack(side="left")

        divider = ctk.CTkFrame(settings_frame, height=1, fg_color="#4A4A4A")
        divider.pack(fill="x", padx=15, pady=(0, 15))

        # -------------------------
        # Target Router Settings
        # -------------------------

        ctk.CTkLabel(
            settings_frame,
            text="Target Router Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(0, 10))

        target_grid = ctk.CTkFrame(settings_frame, fg_color="transparent")
        target_grid.pack(fill="x", padx=15, pady=(0, 15))

        labels = [
            "Host / IP",
            "Username",
            "Password",
            "NETCONF Port",
            "RESTCONF Port"
        ]

        for i, text in enumerate(labels):
            ctk.CTkLabel(
                target_grid,
                text=text,
                font=ctk.CTkFont(size=12),
                text_color="gray75"
            ).grid(row=0, column=i, sticky="w", padx=8, pady=(0, 3))

        self.host_entry = ctk.CTkEntry(
            target_grid,
            placeholder_text="Enter hostname or IP"
        )
        self.host_entry.grid(row=1, column=0, padx=8, pady=(0, 10), sticky="ew")
        #self.host_entry.insert(0, "bjornmijs.asuscomm.com")

        self.username_entry = ctk.CTkEntry(
            target_grid,
            placeholder_text="Enter username"
        )
        self.username_entry.grid(row=1, column=1, padx=8, pady=(0, 10), sticky="ew")
        #self.username_entry.insert(0, "bjorn")

        self.password_entry = ctk.CTkEntry(
            target_grid,
            placeholder_text="Enter password",
            show="*"
        )
        self.password_entry.grid(row=1, column=2, padx=8, pady=(0, 10), sticky="ew")

        self.netconf_port_entry = ctk.CTkEntry(
            target_grid,
            placeholder_text="830"
        )
        self.netconf_port_entry.grid(row=1, column=3, padx=8, pady=(0, 10), sticky="ew")
        #self.netconf_port_entry.insert(0, "9097")

        self.restconf_port_entry = ctk.CTkEntry(
            target_grid,
            placeholder_text="443"
        )
        self.restconf_port_entry.grid(row=1, column=4, padx=8, pady=(0, 10), sticky="ew")
        #self.restconf_port_entry.insert(0, "9096")

        for col in range(5):
            target_grid.columnconfigure(col, weight=1)

        # GitHub selector
        select_frame = ctk.CTkFrame(self.main_frame, corner_radius=14)
        select_frame.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(
            select_frame,
            text="GitHub Config Selection",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 8))

        self.config_var = tk.StringVar()
        self.config_dropdown = ctk.CTkOptionMenu(
            select_frame,
            variable=self.config_var,
            values=["Loading configs..."],
            width=620
        )
        self.config_dropdown.pack(anchor="w", padx=15, pady=(0, 15))

        # Buttons
        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.refresh_button = ctk.CTkButton(
            button_frame,
            text="Refresh Configs",
            command=self.load_configs_threaded,
            height=38,
            fg_color="#7C3AED",
            hover_color="#6D28D9"
        )
        self.refresh_button.pack(side="left", padx=(0, 10))

        self.preview_button = ctk.CTkButton(
            button_frame,
            text="Preview Config",
            command=self.preview_config_threaded,
            height=38,
            fg_color="#0891B2",
            hover_color="#0E7490"
        )
        self.preview_button.pack(side="left", padx=(0, 10))

        self.push_button = ctk.CTkButton(
            button_frame,
            text="Push Selected Config",
            command=self.push_config_threaded,
            height=38,
            fg_color="#15803D",
            hover_color="#166534"
        )
        self.push_button.pack(side="left", padx=(0, 10))

        self.export_log_button = ctk.CTkButton(
            button_frame,
            text="Export Log",
            command=self.export_log,
            height=38,
            fg_color="#CA8A04",
            hover_color="#A16207"
        )
        self.export_log_button.pack(side="left", padx=(0, 10))

        self.clear_button = ctk.CTkButton(
            button_frame,
            text="Clear Log",
            command=self.clear_log,
            height=38,
            fg_color="#444444",
            hover_color="#555555"
        )
        self.clear_button.pack(side="left")

        # Progress
        progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        progress_frame.pack(fill="x", padx=20, pady=(5, 10))

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Ready",
            text_color="gray70",
            font=ctk.CTkFont(size=14)
        )
        self.status_label.pack(anchor="w")

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", pady=(5, 0))
        self.progress_bar.set(0)

        # Log
        log_frame = ctk.CTkFrame(self.main_frame, corner_radius=14)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(5, 20))

        ctk.CTkLabel(
            log_frame,
            text="Deployment Log",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 8))

        self.log_box = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=13),
            corner_radius=10
        )
        self.log_box.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    # =========================
    # Helpers
    # =========================

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.root.update_idletasks()

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
        self.push_button.configure(state=state)
        self.export_log_button.configure(state=state)
        self.clear_button.configure(state=state)

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

    # =========================
    # Profiles
    # =========================

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

        self.netconf_port_entry.delete(0, "end")
        self.netconf_port_entry.insert(0, profile.get("netconf_port", "830"))

        self.restconf_port_entry.delete(0, "end")
        self.restconf_port_entry.insert(0, profile.get("restconf_port", "443"))

        self.log(f"Profile loaded with password: {name}")

    # =========================
    # GitHub
    # =========================

    def load_configs_threaded(self):
        threading.Thread(target=self.load_configs, daemon=True).start()

    def load_configs(self):
        try:
            self.set_buttons_state("disabled")
            self.start_loading("Fetching config list from GitHub...")
            self.log("Fetching config list from GitHub...")

            response = requests.get(
                GITHUB_API_URL,
                headers={"Cache-Control": "no-cache"},
                timeout=30
            )
            response.raise_for_status()

            files = response.json()

            self.configs = [
                {
                    "name": item["name"],
                    "download_url": item["download_url"],
                    "type": self.get_config_type(item["name"])
                }
                for item in files
                if item["type"] == "file"
                and item["name"].lower().endswith((".xml", ".json"))
            ]

            if not self.configs:
                self.log("No XML or JSON config files found.")
                self.stop_loading("No configs found.", 0)
                return

            dropdown_values = [
                f"{cfg['name']} ({cfg['type']})"
                for cfg in self.configs
            ]

            self.config_dropdown.configure(values=dropdown_values)
            self.config_var.set(dropdown_values[0])

            self.log(f"Found {len(self.configs)} config file(s).")
            self.stop_loading("Config list loaded.", 1)

        except Exception as error:
            self.stop_loading("Failed to load configs.", 0)
            self.log(f"Failed to load GitHub configs: {error}")
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
        url = config["download_url"] + f"?nocache={time.time()}"

        self.log(f"Downloading config: {config['name']}")
        self.set_status(f"Downloading {config['name']}...", 0.25)

        response = requests.get(
            url,
            headers={
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            },
            timeout=30
        )
        response.raise_for_status()

        content = response.text.strip()

        if config["type"] == "NETCONF" and "noshutdown" in content.lower():
            raise ValueError("Downloaded XML contains unsupported <noshutdown/> tag.")

        return content

    # =========================
    # Preview
    # =========================

    def preview_config_threaded(self):
        threading.Thread(target=self.preview_config, daemon=True).start()

    def preview_config(self):
        try:
            self.set_buttons_state("disabled")

            config = self.get_selected_config()

            self.start_loading(
                f"{config['type']} detected - previewing {config['name']}..."
            )

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
            text="Copy to Clipboard",
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

    # =========================
    # Deployment
    # =========================

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

            self.start_loading(
                f"{config['type']} detected - deploying {config['name']}..."
            )

            self.log(f"{config['type']} detected based on file extension.")
            self.log(f"Target router: {router['host']}")

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

    # =========================
    # NETCONF
    # =========================

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

    # =========================
    # RESTCONF
    # =========================

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

    # =========================
    # Log Export
    # =========================

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


def main():
    root = ctk.CTk()
    ModernConfigPushGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()