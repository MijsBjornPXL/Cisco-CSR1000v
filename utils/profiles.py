import json
import os

from constants import PROFILE_FILE, DEFAULT_GITHUB_API_URL


def get_default_app_data():
    return {
        "settings": {
            "github_api_url": DEFAULT_GITHUB_API_URL
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


def ensure_profile_file_exists():
    if os.path.exists(PROFILE_FILE):
        return

    save_app_data(get_default_app_data())


def load_app_data():
    if not os.path.exists(PROFILE_FILE):
        default_data = get_default_app_data()
        save_app_data(default_data)
        return default_data

    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        # Backward compatibility with old format
        if "profiles" not in data:
            data = {
                "settings": {
                    "github_api_url": DEFAULT_GITHUB_API_URL
                },
                "profiles": data
            }
            save_app_data(data)

        if "settings" not in data:
            data["settings"] = {}

        data["settings"].setdefault("github_api_url", DEFAULT_GITHUB_API_URL)
        data.setdefault("profiles", {})

        return data

    except Exception:
        default_data = get_default_app_data()
        save_app_data(default_data)
        return default_data


def save_app_data(data):
    with open(PROFILE_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def load_profiles_from_file():
    return load_app_data().get("profiles", {})


def save_profiles_to_file(profiles):
    data = load_app_data()
    data["profiles"] = profiles
    save_app_data(data)


def get_github_api_url():
    return load_app_data().get("settings", {}).get(
        "github_api_url",
        DEFAULT_GITHUB_API_URL
    )


def set_github_api_url(url):
    data = load_app_data()
    data.setdefault("settings", {})
    data["settings"]["github_api_url"] = url
    save_app_data(data)