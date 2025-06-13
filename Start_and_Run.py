
import os
import json
import subprocess
import platform

ENV_PATH = ".env"
CREDENTIALS_PATH = "credentials/credentials.json"
EBAY_KEYS_PATH = "credentials/ebay_keys.json"

def ask(prompt, default=""):
    val = input(f"{prompt} [{default}]: ").strip()
    return val if val else default

def confirm_or_edit(var_name, current_value):
    print(f"\n{var_name}: {current_value}")
    answer = input("Is this correct? (Y/n): ").strip().lower()
    if answer == 'n':
        return input(f"Enter new value for {var_name}: ").strip()
    return current_value

def load_env():
    env = {}
    if os.path.isfile(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    env[k] = v
    return env

def append_env(env):
    existing = load_env()
    with open(ENV_PATH, "a") as f:
        for k, v in env.items():
            if k not in existing:
                f.write(f"{k}={v}\n")

def check_json(path, required_keys):
    if not os.path.exists(path):
        print(f"Missing file: {path}")
        return {}
    with open(path) as f:
        data = json.load(f)
    for k in required_keys:
        if k not in data:
            print(f"Missing key '{k}' in {path}")
    return data

def update_json(path, data):
    existing = {}
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)
    existing.update(data)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(existing, f, indent=2)

def setup_venv_and_requirements():
    py_exec = "python" if platform.system() == "Windows" else "python3"
    pip_exec = "venv\\Scripts\\pip.exe" if platform.system() == "Windows" else "venv/bin/pip"
    if not os.path.isdir("venv"):
        print("Creating virtual environment...")
        subprocess.run([py_exec, "-m", "venv", "venv"])
    print("Installing dependencies...")
    subprocess.run([pip_exec, "install", "-r", "requirements.txt"])

def run_flask():
    flask_exec = "venv\\Scripts\\python.exe" if platform.system() == "Windows" else "venv/bin/python"
    subprocess.run([flask_exec, "app.py"])

def smart_cli_installer():
    print("Manifest App CLI Installer")

    env_vars = load_env()
    expected_keys = [
        "SESSION_SECRET", "GOOGLE_CREDS_PATH", "SUMMARY_SHEET_URL",
        "EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET"
    ]
    updated_env = {}
    for key in expected_keys:
        current = env_vars.get(key, "")
        updated_env[key] = confirm_or_edit(key, current)
    append_env(updated_env)
    print(".env file updated or appended.")

    creds = check_json(CREDENTIALS_PATH, ["private_key", "client_email", "token_uri"])
    if creds:
        print(f"Google Service Account Email: {creds.get('client_email')}")
        if input("Use existing Google credentials.json? (Y/n): ").lower() == "n":
            path = ask("Path to new Google credentials.json")
            new_data = json.load(open(path))
            update_json(CREDENTIALS_PATH, new_data)
            print("Google credentials updated.")
    else:
        path = ask("Path to Google credentials.json")
        new_data = json.load(open(path))
        update_json(CREDENTIALS_PATH, new_data)

    ebay_keys = check_json(EBAY_KEYS_PATH, ["app_id", "cert_id", "dev_id"])
    updated_keys = {}
    for k in ["app_id", "cert_id", "dev_id"]:
        updated_keys[k] = confirm_or_edit(k.upper(), ebay_keys.get(k, ""))
    update_json(EBAY_KEYS_PATH, updated_keys)
    print("eBay keys updated.")

    setup_venv_and_requirements()
    if input("Run the app now? (Y/n): ").lower() != "n":
        run_flask()

if __name__ == "__main__":
    smart_cli_installer()
