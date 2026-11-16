#!/usr/bin/env python3
"""Tests for license_year_checker — stdlib unittest only."""

import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import license_year_checker as checker

REPO = Path(__file__).resolve().parent.parent

MIT = ("MIT License\n\nCopyright (c) %s Example Person\n\n"
       "Permission is hereby granted, free of charge.\n")


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)
    return str(path)


class TestCheckText(unittest.TestCase):
    def test_current_year_passes(self):
        self.assertEqual(
            checker.check_text(MIT % "2026", current_year=2026), [])

    def test_original_year_passes(self):
        # A project keeping its original year is correct
        # by its own policy — the weaker rule on purpose.
        self.assertEqual(
            checker.check_text(MIT % "2024", current_year=2026), [])
        self.assertEqual(
            checker.check_text(MIT % "2019", current_year=2026), [])

    def test_future_year_fails(self):
        findings = checker.check_text(MIT % "2027", current_year=2026)
        self.assertEqual(findings, [
            {"line": 3, "year": 2027,
             "reason": "copyright year 2027 is in the future"}])

    def test_far_future_year_fails(self):
        findings = checker.check_text(MIT % "2099", current_year=2026)
        self.assertEqual(findings[0]["year"], 2099)
        self.assertEqual(findings[0]["line"], 3)

    def test_missing_year_fails(self):
        findings = checker.check_text(MIT % "Example Person",
                                      current_year=2026)
        self.assertEqual(findings, [
            {"line": 3, "year": None,
             "reason": "no copyright year found"}])

    def test_no_copyright_line_fails_at_line_1(self):
        findings = checker.check_text(
            "MIT License\n\nPermission is hereby granted.\n",
            current_year=2026)
        self.assertEqual(findings, [
            {"line": 1, "year": None,
             "reason": "no copyright year found"}])

    def test_empty_file_fails(self):
        findings = checker.check_text("", current_year=2026)
        self.assertEqual(findings, [
            {"line": 1, "year": None,
             "reason": "no copyright year found"}])

    def test_year_range_judged_by_latest_year(self):
        text = ("MIT License\n\n"
                "Copyright (c) 2019-2024 Example Person\n")
        self.assertEqual(checker.check_text(text, current_year=2026), [])
        text = ("MIT License\n\n"
                "Copyright (c) 2019-2099 Example Person\n")
        findings = checker.check_text(text, current_year=2026)
        self.assertEqual(findings[0]["year"], 2099)

    def test_year_off_copyright_line_ignored(self):
        text = ("MIT License\n\n"
                "Copyright (c) 2024 Example Person\n\n"
                "Version 2099 of this license text.\n")
        self.assertEqual(checker.check_text(text, current_year=2026), [])

    def test_year_without_copyright_word_ignored(self):
        text = "MIT License\n\nPublished in 2099.\n"
        findings = checker.check_text(text, current_year=2026)
        self.assertEqual(findings[0]["reason"], "no copyright year found")

    def test_case_insensitive_copyright(self):
        text = "COPYRIGHT (C) 2024 EXAMPLE PERSON\n"
        self.assertEqual(checker.check_text(text, current_year=2026), [])
        text = "copyright 2099 someone\n"
        findings = checker.check_text(text, current_year=2026)
        self.assertEqual(findings[0]["year"], 2099)

    def test_apache_style_placeholder_year(self):
        text = ("Copyright [yyyy] [name of copyright owner]\n")
        findings = checker.check_text(text, current_year=2026)
        self.assertEqual(findings[0]["reason"], "no copyright year found")

    def test_multiple_copyright_lines_worst_wins(self):
        text = ("Copyright (c) 2020 First Person\n"
                "Copyright (c) 2099 Second Person\n")
        findings = checker.check_text(text, current_year=2026)
        self.assertEqual(findings[0]["year"], 2099)
        self.assertEqual(findings[0]["line"], 2)

    def test_year_before_1900_not_a_year(self):
        text = "Copyright (c) 1899 Example Person\n"
        findings = checker.check_text(text, current_year=2026)
        self.assertEqual(findings[0]["reason"], "no copyright year found")

    def test_three_digit_number_not_a_year(self):
        text = "Copyright (c) 999 Example Person\n"
        findings = checker.check_text(text, current_year=2026)
        self.assertEqual(findings[0]["reason"], "no copyright year found")

    def test_five_digit_number_not_a_year(self):
        text = "Copyright (c) 20245 Example Person\n"
        findings = checker.check_text(text, current_year=2026)
        self.assertEqual(findings[0]["reason"], "no copyright year found")

    def test_repo_own_license_passes(self):
        text = (REPO / "LICENSE").read_text()
        self.assertEqual(checker.check_text(text), [])


class TestCheckFile(unittest.TestCase):
    def test_clean_file_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "LICENSE", MIT % "2024")
            findings, error = checker.check_file(path)
            self.assertEqual((findings, error), ([], None))

    def test_future_file_reports_line_and_year(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "LICENSE", MIT % "2099")
            findings, error = checker.check_file(path)
            self.assertEqual(error, None)
            self.assertEqual(findings, [
                {"line": 3, "year": 2099,
                 "reason": "copyright year 2099 is in the future"}])

    def test_missing_file_reports_error(self):
        findings, error = checker.check_file(
            str(Path(tempfile.gettempdir())
                / "no-such-license-year-file"))
        self.assertEqual(findings, [])
        self.assertIsNotNone(error)

    def test_non_utf8_file_reports_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "LICENSE", b"Copyright \xff\xfe 2024\n")
            findings, error = checker.check_file(path)
            self.assertEqual(findings, [])
            self.assertEqual(error, "not valid UTF-8")


class TestCli(unittest.TestCase):
    def test_clean_file_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "LICENSE", MIT % "2024")
            code, out, _err = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn("OK — 1 file(s) checked", out)

    def test_future_year_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "LICENSE", MIT % "2099")
            code, out, _err = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("copyright year 2099 on line 3 is in the future",
                          out)
            self.assertIn("Checked 1 file(s), 1 file(s) with a "
                          "license-year problem.", out)

    def test_missing_year_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "LICENSE", MIT % "Example Person")
            code, out, _err = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("line 3 has no copyright year", out)

    def test_folder_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "LICENSE", MIT % "2024")
            write(tmp, "LICENSE.txt", MIT % "2099")
            write(tmp, "README.md", MIT % "2099")
            code, out, _err = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("LICENSE.txt", out)
            self.assertNotIn("README.md", out)
            self.assertIn("Checked 2 file(s), 1 file(s) with a "
                          "license-year problem.", out)

    def test_licence_spelling_walked(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "LICENCE", MIT % "2099")
            code, out, _err = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("LICENCE", out)

    def test_nested_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "sub/LICENSE", MIT % "2099")
            code, out, _err = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("sub", out)

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "LICENSE", MIT % "2024")
            write(tmp, "sub/LICENSE", MIT % "2099")
            code, out, _err = run_cli(["--no-recursive", tmp])
            self.assertEqual(code, 0)
            self.assertIn("OK — 1 file(s) checked", out)

    def test_exclude(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "LICENSE", MIT % "2099")
            write(tmp, "skip/LICENSE", MIT % "2099")
            code, out, _err = run_cli(["--exclude", "skip", tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 1 file(s)", out)

    def test_git_folder_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, ".git/LICENSE", MIT % "2099")
            write(tmp, "LICENSE", MIT % "2024")
            code, out, _err = run_cli([tmp])
            self.assertEqual(code, 0)

    def test_direct_file_checked_whatever_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "notice.txt", MIT % "2099")
            code, out, _err = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("notice.txt", out)

    def test_duplicate_paths_checked_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "LICENSE", MIT % "2099")
            code, out, _err = run_cli([path, path])
            self.assertEqual(code, 1)
            self.assertEqual(out.count("copyright year 2099"), 1)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "LICENSE", MIT % "2099")
            code, out, _err = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["findings"], 1)
            self.assertEqual(data["files"][0]["findings"], [
                {"line": 3, "year": 2099,
                 "reason": "copyright year 2099 is in the future"}])
            self.assertIsNone(data["files"][0]["error"])

    def test_stdin_flagged(self):
        out = io.StringIO()
        err = io.StringIO()
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO(MIT % "2099")
            with redirect_stdout(out), redirect_stderr(err):
                code = checker.main(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 1)
        self.assertIn("copyright year 2099 on line 3 is in the future",
                      out.getvalue())

    def test_stdin_clean(self):
        out = io.StringIO()
        err = io.StringIO()
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO(MIT % "2024")
            with redirect_stdout(out), redirect_stderr(err):
                code = checker.main(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn("OK — 1 file(s) checked", out.getvalue())

    def test_stdin_with_path_is_usage_error(self):
        code, _out, err = run_cli(["--stdin", "LICENSE"])
        self.assertEqual(code, 2)

    def test_bad_flag(self):
        code, _out, _err = run_cli(["--no-such-flag", "LICENSE"])
        self.assertEqual(code, 2)

    def test_missing_path(self):
        code, _out, err = run_cli(["no-such-folder-xyz"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _out, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no LICENSE files found", err)

    def test_no_paths(self):
        code, _out, _err = run_cli([])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _err = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("license_year_checker 1.0.0", out)

    def test_unreadable_file_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "LICENSE", MIT % "2024")
            os.chmod(path, 0)
            try:
                code, out, _err = run_cli([path])
                if os.geteuid() == 0:
                    self.assertEqual(code, 0)
                else:
                    self.assertEqual(code, 1)
                    self.assertIn("FAIL", out)
            finally:
                os.chmod(path, 0o644)

    def test_input_files_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "LICENSE", MIT % "2099")
            run_cli([path])
            self.assertEqual(Path(path).read_text(), MIT % "2099")

    def test_tool_runs_from_a_temp_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "LICENSE", MIT % "2099")
            result = subprocess.run(
                [sys.executable,
                 str(REPO / "src/license_year_checker.py"), "LICENSE"],
                cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("copyright year 2099 on line 3 is in the future",
                          result.stdout)

    def test_tool_runs_from_root(self):
        result = subprocess.run(
            [sys.executable,
             str(REPO / "src/license_year_checker.py"),
             str(REPO / "LICENSE")],
            cwd="/", capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)


class TestExamples(unittest.TestCase):
    def test_run_example_output_matches_sample(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        expected = (REPO / "examples/sample-output.md").read_text()
        self.assertEqual(result.stdout, expected)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        clean = subprocess.run(
            [sys.executable, "src/license_year_checker.py",
             "examples/LICENSE-clean"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(clean.returncode, 0)
        self.assertIn(clean.stdout.strip(), readme)
        flagged = subprocess.run(
            [sys.executable, "src/license_year_checker.py",
             "examples/LICENSE-flagged"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(flagged.returncode, 1)
        self.assertIn(flagged.stdout.strip(), readme)
        missing = subprocess.run(
            [sys.executable, "src/license_year_checker.py",
             "examples/LICENSE-missing"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(missing.returncode, 1)
        self.assertIn(missing.stdout.strip(), readme)
        edge = subprocess.run(
            [sys.executable, "src/license_year_checker.py",
             "examples/LICENSE-edge"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(edge.returncode, 0)
        self.assertIn(edge.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, "src/license_year_checker.py",
             "examples/"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(folder.returncode, 1)
        self.assertIn("Checked 4 file(s), 2 file(s) with a "
                      "license-year problem.", folder.stdout)
        self.assertIn("Checked 4 file(s), 2 file(s) with a "
                      "license-year problem.", readme)
        js = subprocess.run(
            [sys.executable, "src/license_year_checker.py",
             "--json", "examples/LICENSE-flagged"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(js.returncode, 1)
        self.assertIn(js.stdout.strip(), readme)
        stdin = subprocess.run(
            [sys.executable, "src/license_year_checker.py", "--stdin"],
            input=MIT % "2024", cwd=REPO, capture_output=True, text=True)
        self.assertEqual(stdin.returncode, 0)
        self.assertIn(stdin.stdout.strip(), readme)


class TestHygiene(unittest.TestCase):
    def _repo_files(self, skip_tests=True, skip_examples=True):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")
                       and not (skip_tests and d == "tests")
                       and not (skip_examples and d == "examples")]
            for name in files:
                if name.endswith(".pyc"):
                    continue
                yield Path(root) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=False):
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=False):
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\", "/tmp/"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        stdlib = set(sys.stdlib_module_names)
        for target in (REPO / "src/license_year_checker.py",
                       REPO / "tests/test_license_year_checker.py"):
            tree = ast.parse(target.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(
                imported - stdlib - {"license_year_checker"},
                (target.name, imported))
            self.assertNotIn("yaml", imported)

    def test_no_network_use_in_src(self):
        src = (REPO / "src/license_year_checker.py").read_text()
        for marker in ("urllib.request", "requests", "socket",
                       "http.client", "urlopen", "urlretrieve"):
            self.assertNotIn(marker, src, marker)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github/workflows/ci.yml").read_text()
        self.assertIn("tests/test_license_year_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)

    def test_readme_names_the_neighbouring_repos(self):
        readme = (REPO / "README.md").read_text()
        self.assertIn("license-match-checker-cli", readme)
        self.assertIn("license-header-checker-cli", readme)
        self.assertIn("original year", readme)


if __name__ == "__main__":
    unittest.main()
