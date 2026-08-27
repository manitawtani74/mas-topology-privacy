"""
render_html.py — render writeup.md -> writeup.html, with figures embedded as base64 so the
HTML is a single self-contained file. Requires `markdown` (pip install markdown, or the
project's [docs] extra). Run: python -m experiments.analysis.render_html
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]

CSS = """
:root { color-scheme: light dark; }
body { max-width: 820px; margin: 2rem auto; padding: 0 1.2rem;
  font: 16px/1.65 -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  color: #1a1a1a; background: #fff; }
@media (prefers-color-scheme: dark) { body { color: #e6e6e6; background: #16181d; } }
h1 { font-size: 1.7rem; line-height: 1.25; } h2 { margin-top: 2rem; border-bottom: 1px solid #8883; padding-bottom: .2rem; }
h3 { margin-top: 1.4rem; } img { max-width: 100%; height: auto; border: 1px solid #8883; border-radius: 6px; }
table { border-collapse: collapse; width: 100%; display: block; overflow-x: auto; margin: 1rem 0; }
th, td { border: 1px solid #8884; padding: .35rem .6rem; text-align: left; font-size: .92em; }
code { background: #8881; padding: .1em .35em; border-radius: 4px; font-size: .9em; }
pre { background: #8881; padding: .8rem 1rem; border-radius: 8px; overflow-x: auto; }
pre code { background: none; padding: 0; } blockquote { border-left: 3px solid #8886; margin: 1rem 0; padding: .2rem 1rem; color: #8889b0; }
em { color: #667; } @media (prefers-color-scheme: dark) { em { color: #99a; } }
"""


def _embed(m: re.Match) -> str:
    rel = m.group(1)
    p = ROOT / rel
    if p.exists():
        b64 = base64.b64encode(p.read_bytes()).decode()
        return f"](data:image/png;base64,{b64})"
    return m.group(0)


def main() -> None:
    md_text = (ROOT / "writeup.md").read_text(encoding="utf-8")
    md_text = re.sub(r"\]\((figures/[^)]+\.png)\)", _embed, md_text)
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    title = "Incidental Privacy Leakage vs. Communication Topology in a Cooperative MAS"
    html = (f"<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
            f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{title}</title>\n<style>{CSS}</style>\n</head>\n<body>\n{body}\n</body></html>\n")
    out = ROOT / "writeup.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size // 1024} KB, figures embedded)")


if __name__ == "__main__":
    main()
