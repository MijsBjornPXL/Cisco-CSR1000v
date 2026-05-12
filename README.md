# Cisco Config Deployer

Repository containing configuration files, automation examples, and a modern deployment GUI for Cisco network devices supporting **NETCONF** and **RESTCONF**.

## 📘 Overview

This repository is used to store and manage reusable Cisco configurations for labs, testing environments, and network automation assignments.

The goal is to keep configurations centralized, version-controlled, and easy to deploy through automation tools or the included GUI.

Supported devices typically include Cisco IOS-XE platforms such as routers, switches, virtual appliances, and other devices with NETCONF and/or RESTCONF enabled.

---

## 📂 Repository Structure

```text
Cisco-Config-Deployer/
│
├── Configs/                       # XML / JSON configuration files
├── Scripts/
│   └── Cisco_Config_Deployer.py  # GUI deployment tool
└── README.md                     # Project documentation
```

---

## ⚙️ Included Configurations

Examples may include:

- Hostname configuration
- Interface IP addressing
- VLAN interfaces
- OSPF routing
- Static routes
- RESTCONF compatible configs
- NETCONF compatible configs
- Full IOS-XE lab deployments

---

## ✅ Prerequisites

Before using this tool, ensure the following requirements are met:

### Device Requirements

- Cisco device with **NETCONF** and/or **RESTCONF** support
- Reachable IP address or hostname
- Correct management ports open
- Valid username and password
- Management interface accessible from your PC

### Cisco Configuration Example

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

### Common Default Ports

| Protocol | Default Port |
|--------|--------------|
| NETCONF | 830 |
| RESTCONF HTTPS | 443 |

> Custom ports can also be used in the GUI.

### Python Requirements

Install required modules:

```bash
pip install customtkinter requests ncclient
```

---

## 🖥 Included Deployment Tool

This repository also includes a modern Python GUI called:

**Cisco Config Deployer**

The tool automatically connects to this GitHub repository, detects available config files, and allows direct deployment to supported Cisco devices.

### Features

- Auto-load configs from GitHub
- Detect NETCONF (`.xml`) configs
- Detect RESTCONF (`.json`) configs
- Config preview window
- Push config directly to device
- Device profiles
- Save and load profiles
- Deployment confirmation popup
- Progress bar and live logging
- Export deployment logs
- Modern dark-mode interface

---

## 🚀 Use Cases

This repository can be used for:

- Cisco lab environments
- Network automation testing
- RESTCONF deployments
- NETCONF deployments
- GitHub as Single Source of Truth
- Infrastructure as Code practice
- GUI-based config deployment demos
- Multi-device testing environments

---

## 🔄 Example Workflow

1. Store desired device configuration in this repository
2. Open the Cisco Config Deployer GUI
3. Load or create a device profile
4. Select a config from GitHub
5. Preview configuration
6. Push config via RESTCONF or NETCONF
7. Validate changes
8. Export logs if needed

---

## 🧰 Technologies

- Cisco IOS-XE
- NETCONF
- RESTCONF
- YANG Models
- Python
- CustomTkinter
- GitHub
- Requests
- ncclient

---

## 📌 Notes

- Configurations are intended for educational and lab purposes
- Always verify IP addresses, credentials, and ports before deployment
- Test changes in a non-production environment first
- Saved profiles may store passwords in plain text for lab convenience
- Do not use plain text credential storage in production environments
- Some configuration paths may vary between Cisco platforms and software versions
- Config files are cached locally in the `Configs/` folder.
- GitHub is only contacted when using the `Refresh Configs` button.

---

## 👨‍💻 Author

**Bjorn Mijs**  
GitHub: [MijsBjornPXL](https://github.com/MijsBjornPXL)

---

## ⭐ Version Control

All changes are tracked through GitHub commits for easy rollback, versioning, and collaboration.