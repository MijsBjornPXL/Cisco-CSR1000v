import os
import time

from constants import BACKUP_DIR
from services.netconf_service import get_running_config_netconf
from services.restconf_service import get_running_config_restconf

def backup_running_config(router, config_type, log):
    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    safe_host = router["host"].replace(".", "_")

    log("Creating running-config backup before deployment...")

    if config_type == "NETCONF":
        filename = f"backup_{safe_host}_{timestamp}.xml"
        content = get_running_config_netconf(router)

    elif config_type == "RESTCONF":
        filename = f"backup_{safe_host}_{timestamp}.json"
        content = get_running_config_restconf(router, log)

    elif config_type == "SSH":
        log("SSH config selected. Skipping automatic NETCONF/RESTCONF backup.")
        log("Reason: SSH CLI deployment should not fail when NETCONF is unavailable.")
        return None

    else:
        raise ValueError(f"Unsupported backup config type: {config_type}")

    path = os.path.join(BACKUP_DIR, filename)

    with open(path, "w", encoding="utf-8") as file:
        file.write(content)

    log(f"Backup saved: {path}")
    return path