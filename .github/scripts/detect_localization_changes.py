import os
import json
from pathlib import Path
from github import Github

LOCALIZATION_DIR = Path("assets/base/assets/localization")
EN_PATH = LOCALIZATION_DIR / "en.json"
MAINTAINERS_PATH = Path("localization_maintainers.json")

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_previous_en_json():
    # Get previous version of en.json from Git
    prev_content = os.popen("git show HEAD^:assets/base/assets/localization/en.json").read()
    return json.loads(prev_content)

def compare_dicts(old, new):
    changes = []
    for key in new:
        if key not in old:
            changes.append(f"🆕 Key '{key}' added with text: \"{new[key]}\"")
        elif old[key] != new[key]:
            changes.append(f"✏️ Key '{key}' changed from \"{old[key]}\" to \"{new[key]}\"")
    return changes

def main():
    changed_files = os.popen("git diff --name-only HEAD^ HEAD").read().splitlines()
    if "assets/base/assets/localization/en.json" not in changed_files:
        print("en.json not changed, exiting.")
        return

    if not EN_PATH.exists():
        print("en.json not found in working tree.")
        return

    try:
        prev_en = load_previous_en_json()
    except Exception as e:
        print(f"Failed to load previous en.json: {e}")
        return

    current_en = load_json(EN_PATH)
    changes = compare_dicts(prev_en, current_en)

    if not changes:
        print("No changes in en.json content.")
        return

    maintainers = {}
    if MAINTAINERS_PATH.exists():
        maintainers = load_json(MAINTAINERS_PATH)

    mentions = set()
    for filename, users in maintainers.items():
        if filename != "en.json":
            mentions.update(users)

    issue_title = "🔤 Localization update needed"
    issue_body = (
        "The base localization file `en.json` has been updated. "
        "Please ensure translations are updated accordingly.\n\n"
        "### Summary of changes:\n"
        + "\n".join(f"- {change}" for change in changes)
        + "\n\n"
        + "CC: " + " ".join(mentions)
    )

    token = os.getenv("GITHUB_TOKEN")
    repo_name = os.getenv("GITHUB_REPOSITORY")
    gh = Github(token)
    repo = gh.get_repo(repo_name)

    issue = repo.create_issue(
        title=issue_title,
        body=issue_body,
        assignees=[m.lstrip("@") for m in mentions if m.startswith("@")]
    )

    print(f"Issue created: {issue.html_url}")

if __name__ == "__main__":
    main()
