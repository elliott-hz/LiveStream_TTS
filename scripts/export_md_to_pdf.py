#!/usr/bin/env python3
"""Convert markdown files to PDF.

Usage:
    python3 scripts/export_md_to_pdf.py

Requirements (auto-installed if missing):
    pip3 install markdown weasyprint
"""

import subprocess
import sys
from pathlib import Path


def ensure_deps():
    """Install required packages if not present."""
    deps = ["markdown", "weasyprint"]
    for dep in deps:
        try:
            __import__(dep)
        except ImportError:
            print(f"Installing {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])


def md_to_pdf(md_path: Path) -> Path:
    """Convert a single markdown file to PDF using markdown + weasyprint."""
    import markdown
    from weasyprint import HTML

    pdf_path = md_path.with_suffix(".pdf")

    # Read markdown content
    md_content = md_path.read_text(encoding="utf-8")

    # Convert markdown to HTML
    html_body = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "codehilite", "toc", "nl2br"],
    )

    # Wrap in a styled HTML document
    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 2cm 2.2cm;
    @top-center {{
      content: element(pageHeader);
    }}
  }}
  body {{
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
    font-size: 11pt;
    line-height: 1.7;
    color: #1a1a1a;
  }}
  h1 {{ font-size: 20pt; margin-top: 0; border-bottom: 2px solid #2563eb; padding-bottom: 6px; }}
  h2 {{ font-size: 15pt; margin-top: 28px; border-bottom: 1px solid #d1d5db; padding-bottom: 4px; }}
  h3 {{ font-size: 12pt; margin-top: 20px; }}
  h4 {{ font-size: 11pt; margin-top: 16px; }}
  blockquote {{
    border-left: 3px solid #2563eb;
    margin: 12px 0;
    padding: 8px 16px;
    background: #f8fafc;
    color: #475569;
  }}
  code {{
    background: #f1f5f9;
    padding: 1px 4px;
    border-radius: 3px;
    font-family: "SF Mono", "Fira Code", monospace;
    font-size: 9pt;
  }}
  pre {{
    background: #1e293b;
    color: #e2e8f0;
    padding: 12px 16px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 9pt;
    line-height: 1.5;
  }}
  pre code {{
    background: none;
    padding: 0;
    color: inherit;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 10pt;
  }}
  th, td {{
    border: 1px solid #d1d5db;
    padding: 6px 10px;
    text-align: left;
  }}
  th {{
    background: #f1f5f9;
    font-weight: 600;
  }}
  hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 24px 0; }}
  strong {{ color: #111827; }}
  ul, ol {{ padding-left: 24px; }}
  li {{ margin: 3px 0; }}
  /* checkbox list styling */
  ul li:has(input[type="checkbox"]) {{
    list-style: none;
    margin-left: -24px;
  }}
  input[type="checkbox"] {{
    margin-right: 6px;
  }}
  /* preformatted ASCII art */
  pre code:not([class]) {{
    font-family: "SF Mono", "Fira Code", monospace;
    font-size: 8pt;
    line-height: 1.25;
  }}
  .page-break {{ page-break-before: always; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

    # Generate PDF
    HTML(string=html_doc).write_pdf(str(pdf_path))
    return pdf_path


def main():
    ensure_deps()

    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    files = [
        docs_dir / "尽调清单-章总沟通.md",
        docs_dir / "技术方案与Roadmap-章总沟通.md",
    ]

    for md_file in files:
        if not md_file.exists():
            print(f"⚠ Skipping (not found): {md_file}")
            continue
        print(f"Converting: {md_file.name}")
        pdf_file = md_to_pdf(md_file)
        print(f"  → {pdf_file.name}  ({pdf_file.stat().st_size / 1024:.0f} KB)")

    print("\nDone!")


if __name__ == "__main__":
    main()
