"""
Verify Contribution Script
Checks that PR changes to README.md follow the correct table format,
include required columns, and have valid links.
"""

import re
import sys
import os
import requests

README = "README.md"
BASE_README = "base/README.md"
REPORT_FILE = "validation_report.md"

# Expected table columns in offer tables
EXPECTED_COLS = ["Product", "Benefit", "Duration", "Verification", "Requirements", "Key Limits", "Link"]

# Emoji symbols that should appear in Duration/Verification columns
VALID_DURATION = ["🔄", "⏳", "💰"]
VALID_VERIFICATION = ["🎓", "🛡️", "🐙"]


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_table_rows(content):
    """Extract all table data rows (lines starting with | ** )"""
    rows = []
    for i, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("| **") and stripped.endswith("|"):
            rows.append((i, stripped))
    return rows


def find_new_rows(base_content, pr_content):
    """Find rows that exist in PR but not in base"""
    base_rows = set(row for _, row in extract_table_rows(base_content))
    pr_rows = extract_table_rows(pr_content)
    return [(line_num, row) for line_num, row in pr_rows if row not in base_rows]


def validate_row(line_num, row):
    """Validate a single table row"""
    issues = []
    cols = [c.strip() for c in row.split("|")[1:-1]]

    # Check column count
    if len(cols) != len(EXPECTED_COLS):
        issues.append(f"Line {line_num}: Expected {len(EXPECTED_COLS)} columns, found {len(cols)}")
        return issues

    product, benefit, duration, verification, requirements, limits, link = cols

    # Check product is bold
    if not product.startswith("**") or not product.endswith("**"):
        issues.append(f"Line {line_num}: Product name should be **bold**")

    # Check duration has valid emoji
    if not any(emoji in duration for emoji in VALID_DURATION):
        issues.append(f"Line {line_num}: Duration should contain one of {VALID_DURATION}")

    # Check verification has valid emoji
    if not any(emoji in verification for emoji in VALID_VERIFICATION):
        issues.append(f"Line {line_num}: Verification should contain one of {VALID_VERIFICATION}")

    # Check link format
    if "[🔗](" not in link and "[link](" not in link.lower():
        issues.append(f"Line {line_num}: Link column should use `[🔗](url)` format")

    # Check link is not empty
    link_match = re.search(r'\[.*?\]\((.*?)\)', link)
    if link_match:
        url = link_match.group(1)
        if not url.startswith("http"):
            issues.append(f"Line {line_num}: Link URL should start with http/https")
    else:
        issues.append(f"Line {line_num}: No valid link found")

    # Check benefit is not empty
    if len(benefit) < 5:
        issues.append(f"Line {line_num}: Benefit description seems too short")

    return issues


def check_link(url, timeout=10):
    """Check if a URL is reachable"""
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0 StudentFreebies-Bot/1.0"})
        return resp.status_code < 400
    except Exception:
        try:
            resp = requests.get(url, timeout=timeout, allow_redirects=True,
                               headers={"User-Agent": "Mozilla/5.0 StudentFreebies-Bot/1.0"})
            return resp.status_code < 400
        except Exception:
            return False


def extract_urls_from_rows(rows):
    """Extract URLs from table rows"""
    urls = []
    for line_num, row in rows:
        matches = re.findall(r'\[.*?\]\((https?://[^)]+)\)', row)
        for url in matches:
            urls.append((line_num, url))
    return urls


def main():
    report_lines = []

    try:
        pr_content = read_file(README)
        base_content = read_file(BASE_README)
    except FileNotFoundError as e:
        report_lines.append(f"## ❌ Error\n\nCould not read files: {e}")
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        sys.exit(1)

    new_rows = find_new_rows(base_content, pr_content)

    if not new_rows:
        report_lines.append("## ✅ Verification Passed\n")
        report_lines.append("No new offer rows detected in this PR. If you made other changes, they look good!")
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        sys.exit(0)

    report_lines.append("## 🔍 Contribution Verification Report\n")
    report_lines.append(f"Found **{len(new_rows)} new offer(s)** added:\n")

    all_issues = []
    for line_num, row in new_rows:
        cols = [c.strip() for c in row.split("|")[1:-1]]
        product = cols[0] if cols else "Unknown"
        report_lines.append(f"- **{product.replace('**', '')}** (line {line_num})")
        issues = validate_row(line_num, row)
        all_issues.extend(issues)

    report_lines.append("")

    # Check links
    urls = extract_urls_from_rows(new_rows)
    broken = []
    for line_num, url in urls:
        if not check_link(url):
            broken.append((line_num, url))

    # Report format issues
    if all_issues:
        report_lines.append("### ⚠️ Format Issues\n")
        for issue in all_issues:
            report_lines.append(f"- {issue}")
        report_lines.append("")

    # Report broken links
    if broken:
        report_lines.append("### 🔗 Broken Links\n")
        for line_num, url in broken:
            report_lines.append(f"- Line {line_num}: `{url}` — not reachable")
        report_lines.append("")

    # Summary
    if not all_issues and not broken:
        report_lines.append("### ✅ All Checks Passed!\n")
        report_lines.append("Format is correct and all links are reachable. Ready for review. 🎉")
    else:
        report_lines.append("### 📋 Action Required\n")
        report_lines.append("Please fix the issues above and push again. The bot will re-check automatically.")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    if all_issues or broken:
        sys.exit(1)


if __name__ == "__main__":
    main()
