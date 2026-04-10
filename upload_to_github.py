import urllib.request
import urllib.error
import json
import base64
import os

TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = "jya1park/auction"

def upload_file(local_path, github_path, commit_msg="Add docs"):
    if not os.path.exists(local_path):
        print(f"SKIP (not found): {local_path}")
        return
    with open(local_path, 'rb') as f:
        content = base64.b64encode(f.read()).decode()

    url = "https://api.github.com/repos/{}/contents/{}".format(REPO, github_path)
    headers = {
        "Authorization": "token {}".format(TOKEN),
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            existing = json.loads(resp.read())
            sha = existing.get("sha", "")
    except urllib.error.HTTPError:
        sha = ""

    data = {"message": commit_msg, "content": content}
    if sha:
        data["sha"] = sha

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers=headers,
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            json.loads(resp.read())
            print("OK: {}".format(github_path))
    except urllib.error.HTTPError as e:
        print("Error {}: {} {}".format(github_path, e.code, e.read().decode()))

# PLAN.md
upload_file(r"C:\Users\jya1p\Documents\PLAN.md", "PLAN.md", "Add PLAN.md")

# CLAUDE.md
upload_file(r"C:\Users\jya1p\Documents\courtauction_crawler\CLAUDE.md", "CLAUDE.md", "Add CLAUDE.md")

# docs/ files
docs_base = r"C:\Users\jya1p\Documents\courtauction_crawler\docs"
for fname in ["projectplanner.md", "codedeveloper.md", "codereviewer.md", "tester.md"]:
    fpath = os.path.join(docs_base, fname)
    upload_file(fpath, "docs/{}".format(fname), "Add docs/{}".format(fname))

print("Done.")
