import json
import os
from constants import PROFILE_FILE

def load_profiles_from_file():
    if not os.path.exists(PROFILE_FILE):
        return {}

    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}

def save_profiles_to_file(profiles):
    with open(PROFILE_FILE, "w", encoding="utf-8") as file:
        json.dump(profiles, file, indent=4)