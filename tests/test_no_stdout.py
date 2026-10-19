"""Guard against writing to stdout from the stdio server (corrupts JSON-RPC)."""

import re
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent / "server"

_PRINT = re.compile(r"(?<![\w.])print\s*\(")
_STDOUT = re.compile(r"sys\.stdout")


def _python_files():
    return sorted(SERVER_DIR.rglob("*.py"))


def test_no_print_in_server():
    offenders = []
    for path in _python_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _PRINT.search(line):
                offenders.append(f"{path.relative_to(SERVER_DIR.parent)}:{lineno}: {line.strip()}")
    assert not offenders, "print() found under server/:\n" + "\n".join(offenders)


def test_no_sys_stdout_in_server():
    offenders = []
    for path in _python_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _STDOUT.search(line):
                offenders.append(f"{path.relative_to(SERVER_DIR.parent)}:{lineno}: {line.strip()}")
    assert not offenders, "sys.stdout found under server/:\n" + "\n".join(offenders)
