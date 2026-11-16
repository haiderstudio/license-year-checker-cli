# Security Policy

This tool runs locally, collects no data, sends nothing anywhere, and needs no API key or secret. It only reads the LICENSE files you point it at, and it never rewrites a file and never changes anything. It writes nothing except the report on standard output (and usage errors on standard error). It never fetches a URL: remote addresses are skipped, not opened.

It only reads lines holding the word "copyright" to find the year — a year anywhere else in the file is never judged.

If you find a case where the tool edits a file, flags a year that exists and is not in the future, or passes a license file with a missing or future year, please open an issue describing the exact commands and input.
