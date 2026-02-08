"""
Link Checker Script
Checks all links in README.md and reports broken ones.
Usage:
  python check_links.py         # Check only new/changed links (PR mode)
  python check_links.py --full  # Check all links (weekly mode)
"""

import re
import sys
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

README = "README.md"
REPORT_FILE = "link_report.md"


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_all_links(content):
    """Extract all markdown links from content"""
    links = []
    for i, line in enumerate(content.split("\n"), 1):
        matches = re.findall(r'\[.*?\]\((https?://[^)]+)\)', line)
        for url in matches:
            links.append((i, url))
    return links


def check_link(line_num, url, timeout=15):
    """Check if a URL is reachable, return (line_num, url, status, ok)"""
    headers = {"User-Agent": "Mozilla/5.0 StudentFreebies-LinkChecker/1.0"}
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True, headers=headers)
        if resp.status_code < 400:
            return (line_num, url, resp.status_code, True)
        # Some sites block HEAD, try GET
        resp = requests.get(url, timeout=timeout, allow_redirects=True, headers=headers)
        return (line_num, url, resp.status_code, resp.status_code < 400)
    except requests.exceptions.Timeout:
        return (line_num, url, "TIMEOUT", False)
    except requests.exceptions.ConnectionError:
        return (line_num, url, "CONNECTION_ERROR", False)
    except Exception as e:
        return (line_num, url, str(e)[:50], False)


def main():
    full_mode = "--full" in sys.argv

    try:
        content = read_file(README)
    except FileNotFoundError:
        print(f"❌ {README} not found")
        sys.exit(1)

    links = extract_all_links(content)
    # Deduplicate by URL (keep first occurrence)
    seen = set()
    unique_links = []
    for line_num, url in links:
        if url not in seen:
            seen.add(url)
            unique_links.append((line_num, url))

    print(f"🔍 Checking {len(unique_links)} unique links...")

    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(check_link, ln, url): (ln, url) for ln, url in unique_links}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            status = "✅" if result[3] else "❌"
            print(f"  {status} [{result[2]}] {result[1]}")

    broken = [r for r in results if not r[3]]
    ok = [r for r in results if r[3]]

    report_lines = []
    report_lines.append(f"## Link Check Report\n")
    report_lines.append(f"- **Total links checked:** {len(unique_links)}")
    report_lines.append(f"- **✅ Working:** {len(ok)}")
    report_lines.append(f"- **❌ Broken:** {len(broken)}\n")

    if broken:
        report_lines.append("### Broken Links\n")
        report_lines.append("| Line | URL | Status |")
        report_lines.append("|:-----|:----|:-------|")
        for line_num, url, status, _ in sorted(broken, key=lambda x: x[0]):
            report_lines.append(f"| {line_num} | `{url}` | {status} |")
        report_lines.append("")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    if broken:
        print(f"\n❌ Found {len(broken)} broken link(s)")
        sys.exit(1)
    else:
        print(f"\n✅ All {len(unique_links)} links are healthy!")
        sys.exit(0)


if __name__ == "__main__":
    main()
