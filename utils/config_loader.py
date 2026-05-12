import os
from constants import LOCAL_CONFIG_DIR

def get_config_type(filename):
    filename = filename.lower()

    if filename.endswith(".xml"):
        return "NETCONF"
    if filename.endswith(".json"):
        return "RESTCONF"
    if filename.endswith(".cli"):
        return "SSH"

    return "UNKNOWN"

def load_local_configs():
    os.makedirs(LOCAL_CONFIG_DIR, exist_ok=True)

    configs = []

    for filename in os.listdir(LOCAL_CONFIG_DIR):
        if filename.lower().endswith((".xml", ".json", ".cli")):
            configs.append({
                "name": filename,
                "local_path": os.path.join(LOCAL_CONFIG_DIR, filename),
                "type": get_config_type(filename),
            })

    return configs

def read_config_file(config):
    with open(config["local_path"], "r", encoding="utf-8") as file:
        content = file.read().strip()

    if config["type"] == "NETCONF" and "noshutdown" in content.lower():
        raise ValueError("Local XML contains unsupported <noshutdown/> tag.")

    return content