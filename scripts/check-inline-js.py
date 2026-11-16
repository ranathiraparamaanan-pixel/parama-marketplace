#!/usr/bin/env python3
"""Extract and syntax-check inline JavaScript in index.html without third-party deps."""
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import tempfile

class Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.current = None
        self.items = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        attrs = dict(attrs)
        if attrs.get("src"):
            self.current = None
            return
        kind = (attrs.get("type") or "").lower()
        if kind in {"application/json", "application/ld+json", "importmap"}:
            self.current = None
            return
        self.current = []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.current is not None:
            code = "".join(self.current).strip()
            if code:
                self.items.append(code)
            self.current = None

html = Path("index.html").read_text(encoding="utf-8")
parser = Scripts()
parser.feed(html)
if not parser.items:
    raise SystemExit("No inline JavaScript found to validate")
with tempfile.TemporaryDirectory() as tmp:
    for i, code in enumerate(parser.items, 1):
        path = Path(tmp) / f"inline-{i}.js"
        path.write_text(code, encoding="utf-8")
        result = subprocess.run(["node", "--check", str(path)], text=True, capture_output=True)
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(f"Inline JavaScript block {i} failed syntax validation")
print(f"Validated {len(parser.items)} inline JavaScript block(s).")
