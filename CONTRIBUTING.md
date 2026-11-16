# Contributing

Small, focused improvements are welcome.

- Open an issue first for anything larger than a typo or a clearer example, so the scope can be agreed before work starts.
- Never weaken the safety rules: a missing year and a future year must stay fails, the tool must never edit a file, and only lines holding the word "copyright" are ever read for a year.
- Do not propose the stricter "year must equal the current year" rule: many projects keep their original year on purpose, and that rule would flag repos that are correct by their own policy.
- Every claim in a proposed change must be verifiable: a command must be runnable, a pass or fail must be real, a badge must be true.
- Run `python3 tests/test_license_year_checker.py` before opening a pull request. It must pass.
- Do not add placeholder text, invented features, or copied content without attribution.
- Python standard library only — no new dependency without a reason in the issue.
