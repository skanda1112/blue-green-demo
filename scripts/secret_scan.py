"""Tiny secret scanner for the Secure Git lab (a teaching tool).

Usage:
    python scripts/secret_scan.py       # scan the whole project
    python scripts/secret_scan.py a.py b.txt  # scan only these files

Exit code 0 = clean, 1 = possible secret found.
"""

import os
import re
import sys

# A risky name (api key / secret / token / password), then = or :,
# then a quoted value of 8 or more characters.
CREDENTIAL = re.compile(
    r"(api[_-]?key|secret|token|passwd|password)\w*['\"]?"
    r"\s*[:=]\s*['\"][^'\"\s]{8,}['\"]",
    re.IGNORECASE,
)

PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".deployed"
}

SKIP_FILES = {".env"}  # local-only file, protected by .gitignore


def project_files():
    for folder, dirs, names in os.walk("."):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for name in names:
            if name not in SKIP_FILES:
                yield os.path.normpath(os.path.join(folder, name))


def scan(path):
    findings = []

    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            for number, line in enumerate(handle, start=1):

                if CREDENTIAL.search(line):
                    findings.append(
                        (path, number, "hard-coded credential")
                    )

                if PRIVATE_KEY.search(line):
                    findings.append(
                        (path, number, "private key")
                    )

    except OSError:
        pass

    return findings


def main(paths):
    files = paths if paths else list(project_files())
    findings = []

    for path in files:
        findings.extend(scan(path))

    if not findings:
        print(f"Secret scan passed - {len(files)} file(s) checked.")
        return 0

    print("BLOCKED: possible secret found")

    for path, number, kind in findings:
        print(f" {path}:{number} {kind}")

    print(
        "Remove it, keep it in an environment variable, "
        "and rotate it if it was ever pushed."
    )

    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))