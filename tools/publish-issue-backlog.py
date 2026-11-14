#!/usr/bin/env python3
"""Preview and publish ISSUE-BACKLOG.md draft tasks as GitHub Issues.

DEFAULT is read-only dry-run. --apply is explicit and requires GitHub
Issues enabled, gh CLI authenticated, and a repository selected by
--repo OWNER/REPO. Never run as root on the VPN server: no system
administration or credential files are needed.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent.parent
DEFAULT = HERE / "ISSUE-BACKLOG.md"
HEADING = re.compile(r"(?m)^## (TASK-\d{3}) — \[(P[0123])\] (.+)$")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class Problem(Exception):
    pass


def drafts(text):
    matches = list(HEADING.finditer(text))
    if not matches:
        raise Problem("No TASK-NNN draft headings found")
    results = []
    seen = set()
    for i, match in enumerate(matches):
        id_, priority, title = match.groups()
        if id_ in seen:
            raise Problem("Duplicate task ID " + id_)
        seen.add(id_)
        finish = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end():finish]
        body = re.sub(r"(?s)\n---\s*$", "", body).strip()
        if len(body) < 170:
            raise Problem("Draft body too short for " + id_)
        results.append({
            "id": id_,
            "title": "[" + priority + "] " + title.strip(),
            "body": "Tracking ID: " + id_ + "\n\n" + body
        })
    return results


def gh(arguments, *, stdin=None):
    try:
        result = subprocess.run(["gh", *arguments], input=stdin,
                                text=True, capture_output=True,
                                timeout=90, check=False)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        raise Problem("GitHub CLI not available/responding: " + str(exc)) from exc
    if result.returncode:
        raise Problem("gh command failed (no secrets printed): "
                      + result.stderr.strip()[:350])
    return result.stdout


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backlog", type=Path, default=DEFAULT,
                   help="Markdown backlog; defaults to this checkout")
    p.add_argument("--repo", help="Explicit OWNER/REPO for GitHub publication")
    p.add_argument("--apply", action="store_true",
                   help="Actually create issues; default prints a preview")
    args = p.parse_args()

    if not args.backlog.is_file() or args.backlog.is_symlink():
        raise Problem("Backlog must be a regular source file")
    data = drafts(args.backlog.read_text(encoding="utf-8"))
    print("Backlog tasks:", len(data))
    for entry in data:
        print(entry["id"] + ": " + entry["title"])
    if not args.apply:
        print("DRY RUN — no GitHub API calls and no issues created.")
        print("Enable Issues in repository settings, then use --repo and --apply.")
        return
    if not args.repo or not REPO.fullmatch(args.repo):
        raise Problem("--repo OWNER/REPO is required for --apply")
    if not shutil.which("gh"):
        raise Problem("GitHub CLI gh is not installed (no changes made)")
    enabled = gh(["api", "repos/" + args.repo, "--jq", ".has_issues"]).strip()
    if enabled != "true":
        raise Problem("GitHub Issues are disabled. Enable Settings > General > Features > Issues.")
    raw = gh(["issue", "list", "-R", args.repo, "--state", "all",
              "--limit", "1000", "--json", "title,body,url"])
    try:
        existing = json.loads(raw)
    except ValueError as exc:
        raise Problem("Invalid GitHub issue list response") from exc
    if not isinstance(existing, list) or len(existing) >= 1000:
        raise Problem("Issue listing is incomplete/too large; refuse unsafe duplicate creation")
    ids = {match.group(0) for issue in existing
           for match in re.finditer(r"\bTASK-\d{3}\b", issue.get("body", ""))}
    titles = {issue.get("title", "") for issue in existing}
    created = 0
    for entry in data:
        if entry["id"] in ids or entry["title"] in titles:
            print("SKIP existing:", entry["id"])
            continue
        try:
            output = gh(["issue", "create", "-R", args.repo,
                         "--title", entry["title"], "--body-file", "-"],
                        stdin=entry["body"] + "\n")
        except Problem:
            # The API may have created the issue despite a failed client
            # response. Stop; operator must check GitHub before retry.
            raise Problem("Publication stopped at " + entry["id"] +
                          ". Verify remote state before re-running.")
        url = output.strip().splitlines()[-1] if output.strip() else "(no URL)"
        print("CREATED", entry["id"], url)
        ids.add(entry["id"])
        created += 1
    print("Published", created, "new issues; existing drafts skipped.")


if __name__ == "__main__":
    try:
        main()
    except (Problem, OSError, UnicodeError) as exc:
        sys.exit("ERROR: " + str(exc))
