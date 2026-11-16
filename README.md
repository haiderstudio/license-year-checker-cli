# license-year-checker-cli

Check the copyright year in LICENSE files — the year must exist and must not be in the future — fail CI when it does not. It never edits a file.

[![CI](https://github.com/haiderstudio/license-year-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/license-year-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`license_year_checker` reads each LICENSE file,
finds the copyright year, and reports a missing
year or a future year, with the file and the line.
It exits 1 when any file fails, so it can fail a
CI run. A license file whose year exists and is
not in the future exits 0.

- The rule is deliberately the weaker one: the
  year must EXIST, and it must NOT be in the
  future. A future year in a license is a real
  mistake — a copy-paste from a template dated
  next year, or a fat-fingered digit — and a
  missing year is the commonest license-file gap.
- The stricter rule — "the year must equal the
  current year" — was considered and rejected on
  purpose: many projects keep their ORIGINAL
  year on purpose, and a gate demanding the
  current year would flag repos that are correct
  by their own policy. A 2024 year in 2026 is
  fine, and this tool passes it.
- Only lines holding the word "copyright" are
  read, so a year anywhere else in the file — a
  version number, a date in the license text —
  is never flagged.
- A range such as "2019-2024" is judged by its
  latest year. The year must be a four-digit year
  from 1900 onward.
- A file given directly on the command line is
  always checked, whatever its name. A folder is
  walked for files whose name starts with
  `LICENSE` or `LICENCE` only, recursively by
  default (`--no-recursive` stops at the top
  level). `.git` folders are never walked, and
  directory links are never followed.
- `--json` prints the result as JSON, and `--stdin`
  checks one LICENSE document read from standard
  input.
- A file that cannot be read, or is not valid
  UTF-8, is reported as an error and fails the
  run, instead of being silently skipped.

## Who it is for

Anyone who ships a LICENSE file — which is every
project with a license. A future year looks like
the project is claiming rights it does not have
yet, and a missing year is the gap every license
review catches late. This is the gate that names
the file before it ships.

## What it does NOT do

- It never edits a file. Fixing the year is a
  one-line edit in your editor — this tool only
  reports it.
- It does not check that the license text matches
  a known license. That is repo #70,
  license-match-checker-cli — the text is a
  different check from the year inside it.
- It does not check the copyright header in
  source files. That is repo #56,
  license-header-checker-cli — source-file
  headers are a different check from the year
  inside LICENSE.
- It does not demand the current year. A project
  that keeps its original year on purpose passes,
  by design — see the rule above.
- It never touches the network.

## How this differs

- A fresh search of GitHub on Nov 14, 2026 found
  0 results for `"license-year-checker-cli"` and
  0 results for `license year checker` — a
  completely empty field. No rival checks the
  copyright year in a LICENSE file.
- So the narrow slice stands: the year inside
  LICENSE only, the weaker rule on purpose
  (must exist, must not be in the future),
  per-file reporting with the year and line
  named, a CI exit code, and no edits.

## Install

```sh
git clone https://github.com/haiderstudio/license-year-checker-cli.git
cd license-year-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one LICENSE file:

```sh
python3 src/license_year_checker.py LICENSE
```

A file with a good year passes — including an
original year kept on purpose:

```sh
$ python3 src/license_year_checker.py examples/LICENSE-clean
OK — 1 file(s) checked, every license file has a copyright year that is not in the future.
```

A file with a future year fails, with the file,
the year, and the line:

```sh
$ python3 src/license_year_checker.py examples/LICENSE-flagged
FAIL examples/LICENSE-flagged: copyright year 2099 on line 3 is in the future — fix the year
Checked 1 file(s), 1 file(s) with a license-year problem.
```

A file with no year fails the same way:

```sh
$ python3 src/license_year_checker.py examples/LICENSE-missing
FAIL examples/LICENSE-missing: line 3 has no copyright year — add the year the work was first published
Checked 1 file(s), 1 file(s) with a license-year problem.
```

Check a whole folder (`LICENSE`/`LICENCE` files
only):

```sh
$ python3 src/license_year_checker.py examples/
FAIL examples/LICENSE-flagged: copyright year 2099 on line 3 is in the future — fix the year
FAIL examples/LICENSE-missing: line 3 has no copyright year — add the year the work was first published
Checked 4 file(s), 2 file(s) with a license-year problem.
```

Check one document from standard input:

```sh
$ python3 src/license_year_checker.py --stdin < examples/LICENSE-flagged
FAIL <stdin>: copyright year 2099 on line 3 is in the future — fix the year
Checked 1 file(s), 1 file(s) with a license-year problem.
```

```sh
$ python3 src/license_year_checker.py --stdin < examples/LICENSE-clean
OK — 1 file(s) checked, every license file has a copyright year that is not in the future.
```

Machine-readable output:

```sh
$ python3 src/license_year_checker.py --json examples/LICENSE-flagged
{
  "files": [
    {
      "path": "examples/LICENSE-flagged",
      "findings": [
        {
          "line": 3,
          "year": 2099,
          "reason": "copyright year 2099 is in the future"
        }
      ],
      "error": null
    }
  ],
  "checked": 1,
  "findings": 1
}
```

Exit codes: 0 when every license file has a
copyright year that is not in the future, 1 when
any file has a missing or future year or a file
cannot be read, 2 for a usage error (a missing
path, a bad flag, or no LICENSE files found).

## Examples

A year range is judged by its latest year, and a
stray future year on a line with no "copyright"
word is never flagged — `examples/LICENSE-edge`
has "Copyright (c) 2019-2024" plus a "Version
2099" line, and it passes:

```sh
$ python3 src/license_year_checker.py examples/LICENSE-edge
OK — 1 file(s) checked, every license file has a copyright year that is not in the future.
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_license_year_checker.py
```

The tests cover the year rule (the current year
passes, an original year passes, a future year
fails, a far-future year fails, a missing year
fails, no copyright line fails at line 1, an
empty file fails, a year range judged by its
latest year, a year off a copyright line ignored,
a year with no "copyright" word ignored,
case-insensitive "copyright", an Apache-style
`[yyyy]` placeholder, the worst of several
copyright lines winning, years before 1900 and
three- and five-digit numbers not counted as
years, and this repo's own LICENSE passing), the
CLI (exit 0/1/2, folder walking for `LICENSE`,
`LICENSE.txt` and `LICENCE`, nested folders,
`--no-recursive`, `--exclude`, `.git` skipped, a
direct file checked whatever its name, duplicate
paths checked once, `--json` output, `--stdin`
flagged and clean, `--stdin` with a path refused,
bad flags, missing paths, empty folders, no paths,
`--version`, a non-UTF-8 file reported, input
files left unchanged, the tool run from a temp
folder and from `/`), the bundled examples
(sample output compared byte-for-byte against a
fresh run, and the README-quoted outputs checked
against it), and hygiene checks (no placeholder
text, no absolute paths, stdlib imports only, no
network use in the source, `.env` first in
`.gitignore`, CI file runs the test file, README
names the neighbouring repos).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo.
The idea of a copyright year is not new, and the
rule it checks — the year must exist and must not
be in the future — is the plain reading of what a
license file should hold — but no existing tool
checks the copyright year in a LICENSE file as a
tested command-line gate, as the search above
shows — and every line of code here is original,
built on nothing but Python's standard library.
