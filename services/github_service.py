import os
import requests

from constants import GITHUB_API_URL, LOCAL_CONFIG_DIR

def sync_configs_from_github(log):
    os.makedirs(LOCAL_CONFIG_DIR, exist_ok=True)

    log("Fetching configs from GitHub...")

    response = requests.get(GITHUB_API_URL, timeout=30)
    response.raise_for_status()

    files = response.json()
    downloaded = 0

    for item in files:
        if item["type"] == "file" and item["name"].lower().endswith((".xml", ".json", ".cli")):
            file_resp = requests.get(item["download_url"], timeout=30)
            file_resp.raise_for_status()

            local_path = os.path.join(LOCAL_CONFIG_DIR, item["name"])

            with open(local_path, "w", encoding="utf-8") as file:
                file.write(file_resp.text)

            downloaded += 1

    log(f"Downloaded {downloaded} config(s) from GitHub.")
    return downloaded