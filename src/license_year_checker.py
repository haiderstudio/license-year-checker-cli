#!/usr/bin/env python3
"""Check the copyright year in LICENSE files.

Run: python3 src/license_year_checker.py LICENSE
     python3 src/license_year_checker.py project/
     python3 src/license_year_checker.py --stdin < LICENSE

The rule is deliberately the weaker one: the year
must EXIST, and it must NOT be in the future. A
missing year is reported, and a future year is
reported, with the file and the line, and the tool
exits 1 when any file fails, so it can fail a CI run.
A license file whose year exists and is not in the
future exits 0.

The stricter rule — "the year must equal the current
year" — was considered and rejected on purpose:
many projects keep their ORIGINAL year on purpose,
and a gate demanding the current year would flag
repos that are correct by their own policy. A 2024
year in 2026 is fine. A 2099 year is not — that is
a copy-paste from a template dated next year, or a
fat-fingered digit — and a license file with no year
at all is the commonest license-file gap.

Only lines holding the word "copyright" are read,
so a year anywhere else in the file — a version
number, a date in the license text — is never
flagged. A range such as "2019-2024" is judged by
its latest year. The year must be a four-digit year
from 1900 onward.

It never rewrites a file, never touches the network,
and reads only the files and folders you point it at.
"""

import argparse
import datetime
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

COPYRIGHT_RE = re.compile(r"copyright", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19\d\d|20\d\d)\b")

LICENSE_PREFIXES = ("LICENSE", "LICENCE")


def check_text(text, current_year=None):
    """Check one license document's text.

    Returns a list of findings, each {"line": int,
    "year": int or None, "reason": str}. At most one
    finding per file: a missing year, or the latest
    copyright year when it is in the future.
    """
    if current_year is None:
        current_year = datetime.date.today().year
    lines = text.splitlines()
    copyright_lines = [
        (number, line)
        for number, line in enumerate(lines, 1)
        if COPYRIGHT_RE.search(line)
    ]
    if not copyright_lines:
        return [{"line": 1, "year": None,
                 "reason": "no copyright year found"}]
    found = []
    for number, line in copyright_lines:
        for match in YEAR_RE.finditer(line):
            found.append((int(match.group(1)), number))
    if not found:
        return [{"line": copyright_lines[0][0], "year": None,
                 "reason": "no copyright year found"}]
    year, line = max(found)
    if year > current_year:
        return [{"line": line, "year": year,
                 "reason": "copyright year %d is in the future"
                           % year}]
    return []


def check_file(path, current_year=None):
    """Check one file. Returns (findings, error)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], "not valid UTF-8"
    except OSError as exc:
        return [], str(exc)
    return check_text(text, current_year=current_year), None


def _is_license_file(path):
    name = Path(path).name.upper()
    return name.startswith(LICENSE_PREFIXES)


def collect_files(paths, recursive=True, exclude=None):
    """Expand CLI paths into a sorted list of license files.

    A file given directly is always checked, whatever its
    name. A folder is walked for files whose name starts
    with LICENSE or LICENCE only, recursively by default
    (--no-recursive stops at the top level). .git folders
    are never walked, and directory links are never
    followed.
    """
    exclude = exclude or []
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(str(path))
        elif path.is_dir():
            for dirpath, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if d != ".git"
                    and not any(fnmatch.fnmatch(d, pat) for pat in exclude)
                ]
                for name in files:
                    candidate = Path(dirpath) / name
                    if not _is_license_file(candidate):
                        continue
                    if any(
                        fnmatch.fnmatch(str(candidate), pat)
                        or fnmatch.fnmatch(name, pat)
                        for pat in exclude
                    ):
                        continue
                    found.append(str(candidate))
                if not recursive:
                    break
        else:
            raise FileNotFoundError("no such file or folder: %s" % raw)
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return sorted(unique)


def format_finding(path, finding):
    """One human-readable line for one license-year problem."""
    if finding["year"] is None:
        return ("FAIL %s: line %d has no copyright year — add "
                "the year the work was first published"
                % (path, finding["line"]))
    return ("FAIL %s: copyright year %d on line %d is in the "
            "future — fix the year"
            % (path, finding["year"], finding["line"]))


def run(paths, recursive=True, exclude=None, as_json=False,
        current_year=None):
    """Check paths, print the report, return the exit code."""
    try:
        files = collect_files(paths, recursive=recursive, exclude=exclude)
    except (FileNotFoundError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no LICENSE files found", file=sys.stderr)
        return 2
    results = []
    findings = 0
    files_with_findings = 0
    for path in files:
        bad, error = check_file(path, current_year=current_year)
        count = len(bad) + (1 if error else 0)
        if count:
            findings += count
            files_with_findings += 1
        results.append({"path": path, "findings": bad, "error": error})
    if as_json:
        print(json.dumps(
            {"files": results, "checked": len(files),
             "findings": findings},
            indent=2))
    else:
        for result in results:
            if result["error"]:
                print("FAIL %s: %s" % (result["path"], result["error"]))
            for finding in result["findings"]:
                print(format_finding(result["path"], finding))
        if findings:
            print("Checked %d file(s), %d file(s) with a "
                  "license-year problem." % (len(files),
                                             files_with_findings))
        else:
            print("OK — %d file(s) checked, every license file "
                  "has a copyright year that is not in the "
                  "future." % len(files))
    return 1 if findings else 0


def run_stdin(as_json=False, current_year=None):
    """Check one license document read from standard input."""
    text = sys.stdin.read()
    findings = check_text(text, current_year=current_year)
    count = len(findings)
    if as_json:
        print(json.dumps(
            {"files": [{"path": "<stdin>", "findings": findings,
                        "error": None}],
             "checked": 1, "findings": count},
            indent=2))
    else:
        for finding in findings:
            print(format_finding("<stdin>", finding))
        if count:
            print("Checked 1 file(s), 1 file(s) with a "
                  "license-year problem.")
        else:
            print("OK — 1 file(s) checked, every license file "
                  "has a copyright year that is not in the "
                  "future.")
    return 1 if count else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="license_year_checker",
        description="Check the copyright year in LICENSE "
                    "files: the year must exist and must not "
                    "be in the future. Fail CI when it does "
                    "not. Report-only; it never edits a file.")
    parser.add_argument("paths", nargs="*",
                        help="LICENSE files or folders to walk")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip files or folders matching this pattern "
                             "(repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one LICENSE document from standard "
                             "input")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)
    if args.stdin:
        if args.paths:
            parser.error("--stdin takes no file or folder arguments")
        return run_stdin(as_json=args.json)
    if not args.paths:
        parser.error("give at least one LICENSE file or folder")
    return run(args.paths, recursive=not args.no_recursive,
               exclude=args.exclude, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
