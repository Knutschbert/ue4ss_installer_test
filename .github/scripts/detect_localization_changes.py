import os
import json
from pathlib import Path
from github import Github
from typing import Dict
import sys
import glob
from collections import defaultdict
import pycountry

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
BRANCH = sys.argv[1].split('/')[-1]

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

    renamed = []
    unmatched_added = set(added)
    unmatched_removed = set(removed)

    for old_key in removed:
        old_val = old[old_key]
        for new_key in added:
            if new_key in unmatched_added and old_val == new[new_key]:
                renamed.append((old_key, new_key))
                unmatched_removed.discard(old_key)
                unmatched_added.discard(new_key)
                break

    return unmatched_added, unmatched_removed, changed, renamed

def get_json_difference(old: Dict[str,str], new: Dict[str,str]):
    changes = []
    added, removed, changed, renamed = compare_dicts_new(old, new)
    for oldk, new_k in renamed:
        changes.append(f"🔑 Key '{oldk}' was renamed to '{new_k}'")
    for key in added:
        changes.append(f"🆕 Key '{key}' added with text: \"{new[key]}\"")
    for key in changed:
        changes.append(f"✏️ Key '{key}' changed from \"{old[key]}\" to \"{new[key]}\"")
    for key in removed:
        changes.append(f"❌ Key '{key}' was removed")
    return changes

def get_lang_specific_diff(old: Dict[str,str], new: Dict[str,str]):
    templates = {}
    added_en, removed_en, changed_en, renamed_en = compare_dicts_new(old, new)
    for file_name in glob.glob(str(LOCALIZATION_DIR/"*.json")):
        if file_name.endswith('en.json'):
            continue
        
        js_data = load_json(file_name)
        added, removed, _, renamed = compare_dicts_new(js_data, new)
        # print(file_name.split('\\')[-1], 'also missing ', added - added_en, 'removed', removed - removed_en )
        # create template
        template = {k: js_data.get(k, new[k]) for k,v in new.items()}
        for name_old, name_new in renamed_en:
            if name_old in js_data:
                template[name_new] = js_data[name_old]

        # template = new
        # for k,v in new.items():
        #     if k in js_data:
        #         template[k] = js_data[k]
        # templates[os.path.basename(file_name)] = template
        template_str = json.dumps(template, indent=4, ensure_ascii=False)
        for add in added & added_en:
            template_str = template_str.replace(f'  "{add}":', f'//  "{add}":')
        for add in added - added_en:
            template_str = template_str.replace(f'  "{add}":', f'//⚠️  "{add}":')
        for (old_ren, new_ren) in renamed_en:
            if new_ren not in added:
                template_str = template_str.replace(f'  "{new_ren}":', f'// renamed "{old_ren}" to "{new_ren}"\n  "{new_ren}":')
        
        templates[os.path.basename(file_name)] = (template_str, added - added_en)
    return templates


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

    ment = defaultdict(list)
    for filename, users in maintainers.items():
        for user in users:
            ment[user].append(filename)

    git_rev_head = os.popen("git rev-parse HEAD").read()

    issue_title = "🔤 Localization update needed"
    issue_body = (
        f"The base localization file [en.json](../../blob/{BRANCH}/{EN_PATH_F}) has been updated. "
        "Please ensure translations are updated accordingly.\n\n"
        f"\n\nBranch: [{BRANCH}](../tree/{BRANCH})\n\n"
        f"\n\nStart Commit: [{PREV_COMMIT[:6]}](../commit/{PREV_COMMIT.replace('^','')})\n\n"
        f"\n\nCurrent Commit: [{git_rev_head[:6]}](../commit/{git_rev_head.replace('^','')})\n\n"
        "### Summary of changes:\n"
        + "\n".join(f"- {change}" for change in changes)
        + "\n\n"
        # + "CC: " + " ".join(mentions)
        + "CC:\n" + "\n".join([f' - {k}: {", ".join(v)}' for k, v in ment.items()])
    )

    templates = get_lang_specific_diff(prev_en, current_en)
    
    for key, (template_str, missing) in templates.items():
        part_body = ""

        language_code = key.split('.')[0].upper().split('_')[0]
        country_code = language_code
        country_info = pycountry.languages.get(alpha_2=language_code)
        if country_info is not None:
            country_code = country_info.alpha_2
            country = pycountry.countries.search_fuzzy(country_info.alpha_3)
            if country is not None:
                country_code = country[0].alpha_2
        flag_url = f"https://raw.githubusercontent.com/exyte/FlagAndCountryCode/refs/heads/main/Sources/FlagAndCountryCode/Resources/CountryFlags.xcassets/{country_code}.imageset/{country_code}.png"

        part_body += f"\n\n## {key}\n\n"
        part_body += (
            f"![{country_info}_flag]({flag_url}) [Edit {key} on Github](../edit/{BRANCH}/assets/base/assets/localization/{key})\n\n"
            "\n\n<details>\n\n"
            f"  <summary>Template for <b>{key}</b></summary>\n\n\n\n"
            f"  ```json\n\n  {template_str}\n\n  ```\n\n"
            "</details>\n\n"
        )
        if len(missing):
            part_body += "### Warnings\n\n"
        for key2 in missing:
            part_body+= f"- ⚠️ `{key2}` is missing!\n\n"
        issue_body += part_body


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
