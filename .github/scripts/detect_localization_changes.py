import os
import json
from pathlib import Path
from github import Github
from typing import Dict
import sys

LOCALIZATION_DIR = Path("assets/base/assets/localization")
EN_PATH = LOCALIZATION_DIR / "en.json"
EN_PATH_F = str(EN_PATH).replace('\\', '/')
MAINTAINERS_PATH = Path("localization_maintainers.json")

if len(sys.argv) == 2:
    if os.name == 'nt':
        PREV_COMMIT = "HEAD^^"
    else:
        PREV_COMMIT = "HEAD^"
else:
    PREV_COMMIT = sys.argv[2]
BRANCH = sys.argv[1].split('/')[0]

print(f'Comparing to commit {PREV_COMMIT}')

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_previous_en_json():
    # Get previous version of en.json from Git
    prev_content = os.popen(f"git show {PREV_COMMIT}:{EN_PATH_F}").read()
    return json.loads(prev_content)

def compare_dicts_new(old: Dict[str,str], new: Dict[str,str]):
    old_s = set(old)
    new_s = set(new)
    added = new_s - old_s
    removed = old_s - new_s
    changed = {k for k in new_s & old_s if new[k] != old[k]}

    return added, removed, changed

def get_json_difference(old: Dict[str,str], new: Dict[str,str]):
    changes = []
    added, removed, changed = compare_dicts_new(old, new)
    for key in added:
        changes.append(f"🆕 Key '{key}' added with text: \"{new[key]}\"")
    for key in changed:
        changes.append(f"✏️ Key '{key}' changed from \"{old[key]}\" to \"{new[key]}\"")
    for key in removed:
        changes.append(f"❌ Key '{key}' was removed")
    return changes

def main():
    # changed_files = os.popen("git diff --name-only HEAD^ HEAD").read().splitlines()
    # if "assets/base/assets/localization/en.json" not in changed_files:
    #     print("en.json not changed, exiting.")
    #     return

    if not EN_PATH.exists():
        print("en.json not found in working tree.")
        return

    try:
        prev_en = load_previous_en_json()
    except Exception as e:
        print(f"Failed to load previous en.json: {e}")
        return

    current_en = load_json(EN_PATH)
    # changes = compare_dicts(prev_en, current_en)
    changes = get_json_difference(prev_en, current_en)

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
        f"The base localization file [en.json](../../blob/{BRANCH}/{EN_PATH_F}) has been updated. "
        "Please ensure translations are updated accordingly.\n\n"
        f"\n\nBranch: [{BRANCH}](../tree/{BRANCH})\n\n"
        f"\n\nStart Commit: [{PREV_COMMIT[:6]}](../commit/{PREV_COMMIT})\n\n"
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
