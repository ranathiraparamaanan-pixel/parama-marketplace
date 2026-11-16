#!/usr/bin/env python3
"""Validate inline JavaScript syntax and basic marketplace navigation wiring."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import tempfile


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.current = None
        self.items = []
        self.ids = []
        self.onclick = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if attrs.get("onclick"):
            self.onclick.append(attrs["onclick"])
        if tag.lower() != "script":
            return
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

duplicates = sorted(key for key, count in Counter(parser.ids).items() if count > 1)
if duplicates:
    raise SystemExit("Duplicate HTML id(s): " + ", ".join(duplicates))

source = "\n".join(parser.items)
declared_functions = set(re.findall(
    r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", source
))
missing_handlers = set()
for handler in parser.onclick:
    match = re.match(r"\s*([A-Za-z_$][\w$]*)\s*\(", handler)
    if match and match.group(1) not in declared_functions:
        missing_handlers.add(match.group(1))
if missing_handlers:
    raise SystemExit("onclick references missing function(s): " + ", ".join(sorted(missing_handlers)))

page_ids = set(parser.ids)
created_pages = set(re.findall(
    r"""paramaEnsurePage\(\s*['"]([^'"]+)['"]""", source
))
navigation_targets = set(re.findall(
    r"""showPage\(\s*['"]([^'"]+)['"]\s*\)""", source
))
navigation_targets = {target for target in navigation_targets if not target.startswith("${")}
missing_pages = sorted(
    target for target in navigation_targets
    if target not in page_ids and target not in created_pages
)
if missing_pages:
    raise SystemExit("showPage references missing page(s): " + ", ".join(missing_pages))

with tempfile.TemporaryDirectory() as tmp:
    for i, code in enumerate(parser.items, 1):
        path = Path(tmp) / f"inline-{i}.js"
        path.write_text(code, encoding="utf-8")
        result = subprocess.run(["node", "--check", str(path)], text=True, capture_output=True)
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(f"Inline JavaScript block {i} failed syntax validation")

print(
    f"Validated {len(parser.items)} inline JavaScript block(s), "
    f"{len(parser.ids)} HTML id(s), onclick handlers, and "
    f"{len(navigation_targets)} static page targets."
)
