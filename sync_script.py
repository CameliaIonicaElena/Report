import os
import hashlib
import subprocess

# =========================
# CONFIG
# =========================
REPO_PATH = r"C:\Users\RO10471\repo_spc"

DATA_FILES = [
    "Test-Measurements&Specs.xlsx",
    "Test-Measurements&Specs1.xlsx",
    "Test-Measurements&Specs2.xlsx"
]

STATE_FILE = "last_hash.txt"


# =========================
# HASH FUNCTION
# =========================
def file_hash(filepath):
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# =========================
# LOAD OLD STATE
# =========================
def load_old_hash():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        lines = f.readlines()
    return dict(line.strip().split("|") for line in lines)


# =========================
# SAVE STATE
# =========================
def save_hash(state):
    with open(STATE_FILE, "w") as f:
        for k, v in state.items():
            f.write(f"{k}|{v}\n")


# =========================
# MAIN CHECK
# =========================
def check_changes():
    old = load_old_hash()
    new = {}

    changed = False

    for file in DATA_FILES:
        if not os.path.exists(file):
            print(f"Missing: {file}")
            continue

        h = file_hash(file)
        new[file] = h

        if file not in old or old[file] != h:
            changed = True

    return changed, new


# =========================
# GIT PUSH
# =========================
def git_push():
    os.chdir(REPO_PATH)

    subprocess.run(["git", "add", "."])
    subprocess.run(["git", "commit", "-m", "auto update dataset"])
    subprocess.run(["git", "push"])


# =========================
# RUN
# =========================
changed, new_state = check_changes()

if changed:
    print("Changes detected → pushing to GitHub...")
    git_push()
    save_hash(new_state)
else:
    print("No changes detected.")
