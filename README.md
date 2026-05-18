# Cisco Config Deployer

<p align="center">
  <img src="docs/banner.png" width="100%">
</p>

Modern Python-based deployment tool for Cisco IOS-XE devices supporting:

- NETCONF
- RESTCONF
- SSH CLI deployments
- CSR1000v VM automation
- GitHub configuration syncing

The application provides a centralized **network-as-code** workflow with a modern GUI for deploying, previewing, validating and managing Cisco configurations.

---

# 📘 Overview

Cisco Config Deployer is a modular automation platform built for Cisco IOS-XE lab environments and automation testing.

The project combines:
- YANG-based automation
- GitHub integration
- VM deployment
- Configuration management
- Live deployment logging
- Network automation workflows

Configurations are stored centrally inside a GitHub repository and can automatically be synchronized to the GUI.

Supported configuration formats:
- `.xml` → NETCONF
- `.json` → RESTCONF
- `.cli` → SSH CLI deployment

Repository:

[Cisco-Config-Deployer GitHub Repository](https://github.com/MijsBjornPXL/Cisco-Config-Deployer)

---

# ✨ Features

## Network Automation
- NETCONF configuration deployment
- RESTCONF configuration deployment
- SSH CLI deployment support
- Automatic config type detection
- Running-config retrieval
- Device information lookup
- Configuration preview
- Configuration diff viewer
- Deployment confirmation popup
- Live deployment logging
- Backup running-config before deploy

---

## GitHub Integration
- GitHub API synchronization
- Centralized config repository
- Local config caching
- Config refresh button
- GitHub repository URL configurable through settings

---

## Device Profiles
- Save/load router profiles
- Store:
  - Host/IP
  - Username
  - Password
  - NETCONF port
  - RESTCONF port
- Password visibility toggle

---

## CSR1000v VM Deployment

Integrated VM deployer for Cisco CSR1000v routers using:
- KVM
- libvirt
- QCOW2 cloning
- Dynamic XML generation

Features:
- Clone existing CSR1000v templates
- Automatically generate VM XML
- Generate random MAC addresses
- Start VM automatically
- Detect DHCP lease
- ARP detection fallback
- Bridge subnet ping sweep support
- Automatic management IP detection

Supports:
- `default` / `virbr0`
- `br0` Linux bridge environments

---

## GUI Features
- Modern CustomTkinter interface
- Dark mode compatible
- Cross-platform builds
- Windows executable support
- Linux executable support
- Export deployment logs
- Responsive deployment status bar
- Multi-window preview/diff interface

---

# 📂 Project Structure

```text
Cisco-Config-Deployer/
│
├── main.py
├── gui.py
├── constants.py
│
├── services/
│   ├── netconf_service.py
│   ├── restconf_service.py
│   ├── ssh_service.py
│   ├── github_service.py
│   ├── backup_service.py
│   └── vm_deployer.py
│
├── utils/
│   ├── profiles.py
│   ├── config_loader.py
│   └── network.py
│
├── Configs/
│   ├── *.xml
│   ├── *.json
│   └── *.cli
│
├── backups/
│
├── docs/
│   └── banner.png
│
├── csr1000v_profiles.json
└── README.md
```

---

# ⚙️ Supported Config Types

| Extension | Deployment Method |
|---|---|
| `.xml` | NETCONF |
| `.json` | RESTCONF |
| `.cli` | SSH CLI |

---

# 🔧 Example Cisco IOS-XE Configuration

Enable required APIs on the Cisco device:

```cisco
conf t
!
netconf-yang
!
restconf
!
ip http secure-server
ip http authentication local
!
username admin privilege 15 secret YourPassword
!
end
wr
```

---

# 🌐 Default Ports

| Protocol | Default Port |
|---|---|
| NETCONF | 830 |
| RESTCONF HTTPS | 443 |

Custom ports are fully supported.

---

# ⚙️ Settings & Profile Configuration

The application automatically creates a configuration file on first launch:

```text
csr1000v_profiles.json
```

This file stores:
- GUI settings
- GitHub API URL
- Router profiles

Example:

```json
{
    "settings": {
        "github_api_url": "https://api.github.com/repos/MijsBjornPXL/Cisco-Config-Deployer/contents/Configs?ref=main"
    },

    "profiles": {
        "Example_Router": {
            "host": "10.10.10.10",
            "username": "admin",
            "password": "password",
            "netconf_port": "830",
            "restconf_port": "443"
        }
    }
}
```

---

# 🚀 Example Workflow

1. Launch the GUI
2. Load or create a device profile
3. Synchronize configs from GitHub
4. Select a configuration
5. Preview configuration
6. Compare differences via Diff Viewer
7. Deploy using:
   - NETCONF
   - RESTCONF
   - SSH CLI
8. Validate deployment
9. Export deployment logs if required

---

# 🖥 CSR1000v VM Deployment Workflow

1. Connect to KVM/libvirt host
2. Read base VM XML
3. Clone QCOW2 disk
4. Generate new VM XML
5. Create new MAC addresses
6. Define VM in libvirt
7. Start VM
8. Detect management IP automatically
9. Auto-fill GUI target IP

---

# 🧰 Technologies Used

- Python
- NETCONF
- RESTCONF
- SSH
- Cisco IOS-XE
- YANG Models
- GitHub API
- CustomTkinter
- ncclient
- requests
- Paramiko
- KVM
- libvirt
- QCOW2
- PyInstaller

---

# 📦 Building Standalone Executables

## Windows

```bash
pyinstaller ^
--onefile ^
--windowed ^
--icon=app.ico ^
--name Cisco_Config_Deployer ^
main.py
```

---

## Linux

```bash
pyinstaller \
--onefile \
--windowed \
--icon=app.ico \
--name Cisco_Config_Deployer \
main.py
```

Run executable:

```bash
./dist/Cisco_Config_Deployer
```

---

# 📌 Notes

- Intended for educational and lab environments
- Some YANG paths may differ between IOS-XE versions
- Saved passwords are stored in plain text for lab convenience
- Production credential storage is not implemented
- RESTCONF certificates are ignored for lab usage
- Configurations are cached locally inside `Configs/`
- GitHub synchronization only occurs when manually refreshed

---

# 👨‍💻 Author

**Bjorn Mijs**

GitHub:  
[MijsBjornPXL GitHub Profile](https://github.com/MijsBjornPXL)

---

# ⭐ Version Control

All changes are tracked through GitHub commits for:
- version control
- rollback support
- centralized management
- collaboration
- configuration history