#!/usr/bin/env python3
"""
Blog Editor — P Sai Ramcharan Reddy
=====================================
Run:  python3 blog/editor.py
Open: http://localhost:5500
"""

import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
from datetime import date as Today
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ── Config ────────────────────────────────────────────────────────────────────
BLOG_DIR  = Path(__file__).parent.resolve()
POSTS_DIR = BLOG_DIR / "posts"
ROOT      = BLOG_DIR.parent          # portfolio_website/ root
PORT      = 5500

POSTS_DIR.mkdir(exist_ok=True)

# ── Markdown → HTML ───────────────────────────────────────────────────────────
def md_to_html(text: str) -> str:
    """Converts Markdown to HTML. Uses 'markdown' lib if available, else built-in fallback."""
    try:
        import markdown
        return markdown.markdown(
            text,
            extensions=["fenced_code", "tables", "footnotes", "nl2br"],
        )
    except ImportError:
        pass
    return _builtin_md(text)


def _inline(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*",     r"<em>\1</em>", s)
    s = re.sub(r"`(.+?)`",       r"<code>\1</code>", s)
    s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
    return s


def _builtin_md(text: str) -> str:
    html, para, in_code, in_list = [], [], False, False

    def flush_para():
        if para:
            html.append(f"<p>{'<br>'.join(para)}</p>")
            para.clear()

    def flush_list():
        nonlocal in_list
        if in_list:
            html.append("</ul>")
            in_list = False

    for line in text.splitlines():
        if line.startswith("```"):
            flush_para(); flush_list()
            if in_code:
                html.append("</code></pre>")
                in_code = False
            else:
                lang = line[3:].strip() or "text"
                html.append(f'<pre><code class="lang-{lang}">')
                in_code = True
            continue

        if in_code:
            html.append(line.replace("&", "&amp;").replace("<", "&lt;"))
            continue

        if not line.strip():
            flush_para(); flush_list()
            continue

        # Headings
        m = re.match(r"^(#{1,6}) (.*)", line)
        if m:
            flush_para(); flush_list()
            n = len(m.group(1))
            html.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
            continue

        # Lists
        if re.match(r"^[-*] ", line):
            flush_para()
            if not in_list:
                html.append("<ul>"); in_list = True
            html.append(f"<li>{_inline(line[2:])}</li>")
            continue

        if re.match(r"^\d+\. ", line):
            flush_para(); flush_list()
            html.append(f"<li>{_inline(re.sub(r'^\\d+\\.\\s', '', line))}</li>")
            continue

        # Blockquote
        if line.startswith("> "):
            flush_para(); flush_list()
            html.append(f"<blockquote><p>{_inline(line[2:])}</p></blockquote>")
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}$", line.strip()):
            flush_para(); flush_list()
            html.append("<hr>")
            continue

        para.append(_inline(line))

    flush_para(); flush_list()
    return "\n".join(html)

# ── Front matter ──────────────────────────────────────────────────────────────
def parse_post(path: Path) -> tuple:
    raw = path.read_text("utf-8")
    meta = {
        "title": path.stem.replace("-", " ").title(),
        "date":  "",
        "tags":  "",
        "slug":  path.stem,
        "file":  path.name,
    }
    body = raw
    if raw.startswith("---"):
        try:
            end = raw.index("---", 3)
            for line in raw[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
            body = raw[end + 3:].strip()
        except ValueError:
            pass
    return meta, body


def all_posts() -> list:
    posts = []
    for p in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        meta, _ = parse_post(p)
        posts.append(meta)
    return posts

# ── HTML templates ────────────────────────────────────────────────────────────
_NAV = """<nav class="site-nav">
  <a href="../index.html" class="nav-logo"><div class="nav-dot"></div>randomartist22</a>
  <ul class="nav-links">
    <li><a href="../index.html">Home</a></li>
    <li><a href="../works.html">Works</a></li>
    <li><a href="../contact.html">Contact</a></li>
    <li><a href="index.html" class="active">Blog</a></li>
  </ul>
  <button class="hamburger" id="hamburger" aria-label="Open menu" aria-expanded="false">
    <span class="hamburger-line"></span>
    <span class="hamburger-line"></span>
    <span class="hamburger-line"></span>
  </button>
</nav>
<div class="mobile-menu" id="mobile-menu">
  <ul>
    <li><a href="../index.html">Home</a></li>
    <li><a href="../works.html">Works</a></li>
    <li><a href="../contact.html">Contact</a></li>
    <li><a href="index.html">Blog</a></li>
  </ul>
</div>"""

_SHARED_JS = """<script>
const _h=document.getElementById('hamburger'),_m=document.getElementById('mobile-menu');
_h.addEventListener('click',()=>{const o=_m.classList.toggle('open');_h.classList.toggle('is-open',o);_h.setAttribute('aria-expanded',o)});
document.querySelectorAll('a[href]').forEach(a=>{const href=a.getAttribute('href');if(href&&!href.startsWith('http')&&!href.startsWith('mailto')&&!href.startsWith('#')){a.addEventListener('click',e=>{e.preventDefault();document.body.classList.add('page-exit');setTimeout(()=>window.location.href=a.href,260)})}});
window.addEventListener('pageshow',()=>document.body.classList.remove('page-exit'));
</script>"""

_HEAD = """<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Inter:wght@300;400;500&family=JetBrains+Mono:wght@300;400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../css/style.css">"""

_FOOTER = """<footer class="site-footer">
  <div class="footer-copy">&copy; 2026 P Sai Ramcharan Reddy &mdash; IIT Gandhinagar</div>
  <ul class="footer-links">
    <li><a href="https://github.com/RandomArtist22" target="_blank" rel="noopener">GitHub</a></li>
    <li><a href="https://www.linkedin.com/in/p-sai-ramcharan-reddy/" target="_blank" rel="noopener">LinkedIn</a></li>
    <li><a href="mailto:p.reddy@iitgn.ac.in">Email</a></li>
  </ul>
</footer>"""

POST_CSS = """
.post-header{padding:calc(70px + 10vh) 0 6vh;border-bottom:1px solid var(--bg-3)}
.post-meta{display:flex;align-items:center;gap:2rem;flex-wrap:wrap;margin-bottom:2.5rem}
.post-date{font-family:var(--mono);font-size:.78rem;color:var(--ink-light);letter-spacing:.08em}
.post-tags{display:flex;gap:.5rem;flex-wrap:wrap}
.post-tag{font-family:var(--mono);font-size:.68rem;border:1px solid var(--bg-3);border-radius:2px;padding:2px 8px;color:var(--ink-mid)}
.post-title{font-family:var(--serif);font-size:clamp(2.8rem,6vw,5rem);font-weight:300;line-height:1;letter-spacing:-.03em}
.post-body{padding:8vh 0;max-width:700px}
.post-body h2,.post-body h3{font-family:var(--serif);font-weight:400;color:var(--ink);margin:2.5rem 0 1rem}
.post-body h2{font-size:2rem}.post-body h3{font-size:1.5rem}
.post-body p{font-size:1.05rem;line-height:1.9;color:var(--ink-mid);margin-bottom:1.4rem}
.post-body a{color:var(--accent);text-decoration:underline;text-underline-offset:3px}
.post-body code{font-family:var(--mono);font-size:.88rem;background:var(--bg-2);padding:2px 6px;border-radius:2px}
.post-body pre{background:var(--ink);color:var(--bg);padding:1.5rem;border-radius:2px;overflow-x:auto;margin:1.5rem 0}
.post-body pre code{background:none;padding:0;color:inherit}
.post-body blockquote{border-left:2px solid var(--accent);padding-left:1.5rem;margin:1.5rem 0;font-style:italic;color:var(--ink-mid)}
.post-body ul,.post-body ol{padding-left:1.5rem;margin-bottom:1.4rem}
.post-body li{font-size:1.05rem;line-height:1.9;color:var(--ink-mid)}
.post-body hr{border:none;border-top:1px solid var(--bg-3);margin:2.5rem 0}
.post-nav{padding:4vh 0;border-top:1px solid var(--bg-3)}
.back-link{font-family:var(--mono);font-size:.78rem;color:var(--accent);letter-spacing:.08em;display:inline-flex;align-items:center;gap:.5rem;transition:gap .3s}
.back-link:hover{gap:1rem}
"""

INDEX_CSS = """
.blog-header{padding:calc(70px + 10vh) 0 8vh;border-bottom:1px solid var(--bg-3)}
.blog-title{font-family:var(--serif);font-size:clamp(4rem,8vw,7rem);font-weight:300;letter-spacing:-.03em;line-height:.9}
.blog-title em{font-style:italic;color:var(--accent)}
.blog-intro{font-size:1rem;color:var(--ink-mid);line-height:1.8;max-width:480px;margin-top:2rem}
.posts-list{padding:6vh 0}
.post-item{display:grid;grid-template-columns:130px 1fr;gap:3rem;padding:3vh 0;border-top:1px solid var(--bg-3);align-items:start}
.post-item:last-child{border-bottom:1px solid var(--bg-3)}
.pi-date{font-family:var(--mono);font-size:.75rem;color:var(--ink-light);padding-top:.35rem}
.pi-title{font-family:var(--serif);font-size:1.8rem;font-weight:400;color:var(--ink);margin-bottom:.5rem;transition:color .3s,padding-left .4s cubic-bezier(.76,0,.24,1)}
.pi-content a:hover .pi-title{color:var(--accent);padding-left:.3rem}
.pi-tags{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.4rem}
.pi-tag{font-family:var(--mono);font-size:.67rem;border:1px solid var(--bg-3);border-radius:2px;padding:2px 8px;color:var(--ink-light)}
.empty-state{padding:8vh 0;font-family:var(--serif);font-size:1.5rem;color:var(--ink-light);font-style:italic}
@media(max-width:768px){.post-item{grid-template-columns:1fr;gap:.5rem}}
"""


def build_post_html(meta: dict, body: str) -> str:
    tags_html = "".join(
        f'<span class="post-tag">{t.strip()}</span>'
        for t in meta.get("tags", "").split(",") if t.strip()
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>{_HEAD}
<title>{meta['title']} — Sai Ramcharan</title>
<style>{POST_CSS}</style>
</head>
<body>
{_NAV}
<header class="post-header">
  <div class="container">
    <div class="post-meta">
      <span class="post-date">{meta.get('date', '')}</span>
      <div class="post-tags">{tags_html}</div>
    </div>
    <h1 class="post-title">{meta['title']}</h1>
  </div>
</header>
<main>
  <div class="container">
    <article class="post-body">{md_to_html(body)}</article>
    <div class="post-nav"><a href="index.html" class="back-link">&larr; All posts</a></div>
  </div>
</main>
{_FOOTER}
{_SHARED_JS}
</body>
</html>"""


def build_index_html(posts: list) -> str:
    if not posts:
        posts_html = '<div class="empty-state">No posts yet.</div>'
    else:
        items = []
        for p in posts:
            tags = "".join(
                f'<span class="pi-tag">{t.strip()}</span>'
                for t in p.get("tags", "").split(",") if t.strip()
            )
            items.append(f"""<div class="post-item">
  <div class="pi-date">{p.get('date', '')}</div>
  <div class="pi-content">
    <a href="{p['slug']}.html">
      <div class="pi-title">{p['title']}</div>
    </a>
    <div class="pi-tags">{tags}</div>
  </div>
</div>""")
        posts_html = '<div class="posts-list">' + "\n".join(items) + "</div>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>{_HEAD}
<meta name="description" content="Blog — P Sai Ramcharan Reddy. Writing on AI engineering, building systems, and side projects.">
<title>Blog — Sai Ramcharan</title>
<style>{INDEX_CSS}</style>
</head>
<body>
{_NAV}
<header class="blog-header">
  <div class="container">
    <div class="section-label"><span class="section-label-text">Writing</span></div>
    <h1 class="blog-title">Notes &amp;<br><em>Essays.</em></h1>
    <p class="blog-intro">Writing on AI engineering, building systems, and things I learned from shipping the projects on the Works page.</p>
  </div>
</header>
<main>
  <div class="container">{posts_html}</div>
</main>
{_FOOTER}
{_SHARED_JS}
</body>
</html>"""

# ── Publish (build + git push) ────────────────────────────────────────────────
def do_publish() -> tuple:
    posts = []
    for md in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        meta, body = parse_post(md)
        out = BLOG_DIR / f"{meta['slug']}.html"
        out.write_text(build_post_html(meta, body), "utf-8")
        posts.append(meta)

    (BLOG_DIR / "index.html").write_text(build_index_html(posts), "utf-8")

    result = subprocess.run(
        'git add . && git commit -m "Update blog posts" && git push',
        shell=True, cwd=str(ROOT), capture_output=True, text=True,
    )
    ok  = result.returncode == 0
    log = (result.stdout + result.stderr).strip()
    return ok, log

# ── Editor UI (embedded HTML) ──────────────────────────────────────────────────
EDITOR_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Blog Editor — Sai Ramcharan</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300&family=Inter:wght@300;400;500&family=JetBrains+Mono:wght@300;400&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#F2F4F8;--bg-2:#E7EAF1;--bg-3:#DDE0EA;
  --ink:#1C1E27;--ink-mid:#4A4E5E;--ink-light:#8890A4;
  --accent:#4C7FA6;
  --serif:'Cormorant Garamond',Georgia,serif;
  --sans:'Inter',-apple-system,sans-serif;
  --mono:'JetBrains Mono','Fira Code',monospace;
  --ease:cubic-bezier(.76,0,.24,1);
  --sidebar:230px;
}
html,body{height:100%;overflow:hidden}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-weight:300;display:flex;flex-direction:column;-webkit-font-smoothing:antialiased}

/* ── Top bar ── */
.topbar{height:54px;display:flex;align-items:center;justify-content:space-between;padding:0 1.25rem;background:var(--bg);border-bottom:1px solid var(--bg-3);flex-shrink:0;gap:1rem}
.topbar-logo{font-family:var(--mono);font-size:.78rem;color:var(--ink);display:flex;align-items:center;gap:.6rem;flex-shrink:0}
.logo-dot{width:7px;height:7px;border-radius:50%;background:var(--accent)}
.topbar-right{display:flex;gap:.6rem;align-items:center}

.status{font-family:var(--mono);font-size:.7rem;padding:3px 10px;border-radius:20px;border:1px solid var(--bg-3);color:var(--ink-light);transition:all .3s;white-space:nowrap}
.status.ok{border-color:#5cba8e;color:#5cba8e}
.status.error{border-color:#c97b7b;color:#c97b7b}
.status.busy{border-color:var(--accent);color:var(--accent)}

.btn{font-family:var(--mono);font-size:.72rem;letter-spacing:.05em;border:none;cursor:pointer;padding:7px 14px;border-radius:2px;transition:opacity .2s;white-space:nowrap}
.btn:hover{opacity:.75}
.btn-primary{background:var(--ink);color:var(--bg)}
.btn-ghost{background:transparent;border:1px solid var(--bg-3);color:var(--ink-mid)}
.btn-danger{background:transparent;border:1px solid #c97b7b;color:#c97b7b}

/* ── Layout ── */
.layout{flex:1;display:flex;overflow:hidden}

/* ── Sidebar ── */
.sidebar{width:var(--sidebar);flex-shrink:0;border-right:1px solid var(--bg-3);display:flex;flex-direction:column;background:var(--bg)}
.sidebar-head{padding:.85rem 1rem;border-bottom:1px solid var(--bg-3);display:flex;align-items:center;justify-content:space-between}
.sidebar-label{font-family:var(--mono);font-size:.68rem;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-light)}
.post-list{flex:1;overflow-y:auto;padding:.25rem 0}

.post-row{padding:.7rem 1rem;cursor:pointer;border-left:2px solid transparent;transition:background .15s,border-color .15s}
.post-row:hover{background:var(--bg-2)}
.post-row.active{border-left-color:var(--accent);background:var(--bg-2)}
.pr-title{font-size:.85rem;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:.2rem}
.pr-date{font-family:var(--mono);font-size:.68rem;color:var(--ink-light)}

/* ── Editor pane ── */
.editor-pane{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0}

.meta-bar{padding:.65rem 1.25rem;border-bottom:1px solid var(--bg-3);display:grid;grid-template-columns:1fr 140px 1fr;gap:.75rem}
.meta-input{width:100%;background:transparent;border:none;border-bottom:1px solid var(--bg-3);padding:.35rem 0;font-family:var(--sans);font-size:.9rem;color:var(--ink);outline:none;transition:border-color .2s}
.meta-input:focus{border-bottom-color:var(--accent)}
.meta-input.is-title{font-family:var(--serif);font-size:1.15rem;font-weight:400}
.meta-input::placeholder{color:var(--ink-light)}

.toolbar{padding:.35rem 1.25rem;border-bottom:1px solid var(--bg-3);display:flex;gap:.4rem;align-items:center;flex-wrap:wrap}
.tb{font-family:var(--mono);font-size:.7rem;background:transparent;border:1px solid var(--bg-3);padding:3px 8px;border-radius:2px;cursor:pointer;color:var(--ink-mid);transition:all .15s}
.tb:hover{border-color:var(--accent);color:var(--accent)}
.tb.on{border-color:var(--accent);color:var(--accent)}
.tb-sep{width:1px;height:16px;background:var(--bg-3);flex-shrink:0}

.editor-area{flex:1;display:flex;overflow:hidden}
.editor-wrap{position:relative;flex:1;overflow:hidden;border-right:1px solid var(--bg-3)}
.hl-pre{position:absolute;top:0;left:0;right:0;bottom:0;padding:1.5rem 1.25rem;font-family:var(--mono);font-size:.87rem;line-height:1.75;white-space:pre-wrap;word-break:break-word;overflow:hidden;pointer-events:none;margin:0;border:none;background:transparent;color:var(--ink-mid)}
.md-textarea{position:absolute;top:0;left:0;width:100%;height:100%;padding:1.5rem 1.25rem;font-family:var(--mono);font-size:.87rem;line-height:1.75;color:transparent;caret-color:var(--ink);background:transparent;border:none;resize:none;outline:none;tab-size:4;overflow-y:auto;}
/* syntax token colours */
.hl-h{color:#4C7FA6;font-weight:500}
.hl-bq{color:var(--ink-light);font-style:italic}
.hl-fence,.hl-cb{color:#5b9e7a}
.hl-meta{color:var(--ink-light)}
.hl-ic{color:#5b9e7a}
.hl-bold{color:var(--ink);font-weight:600}
.hl-em{color:var(--ink);font-style:italic}
.hl-link{color:#4C7FA6}
.hl-li{color:var(--ink)}
.preview{flex:1;overflow-y:auto;padding:1.5rem 2rem;display:none;font-family:var(--sans)}
.preview.show{display:block}
.preview h1,.preview h2,.preview h3{font-family:var(--serif);font-weight:400;color:var(--ink);margin:2rem 0 .75rem}
.preview h2{font-size:1.7rem}.preview h3{font-size:1.3rem}
.preview p{font-size:1rem;line-height:1.85;color:var(--ink-mid);margin-bottom:1.2rem}
.preview code{font-family:var(--mono);font-size:.85rem;background:var(--bg-2);padding:2px 5px;border-radius:2px}
.preview pre{background:var(--ink);color:var(--bg);padding:1.2rem;border-radius:2px;overflow-x:auto;margin:1rem 0;font-family:var(--mono);font-size:.85rem}
.preview pre code{background:none;padding:0;color:inherit}
.preview a{color:var(--accent)}
.preview blockquote{border-left:2px solid var(--accent);padding-left:1rem;font-style:italic;color:var(--ink-mid);margin:1rem 0}
.preview li{font-size:1rem;line-height:1.8;color:var(--ink-mid)}
.preview ul,.preview ol{padding-left:1.5rem;margin-bottom:1rem}
.preview hr{border:none;border-top:1px solid var(--bg-3);margin:2rem 0}

/* ── Empty state ── */
.empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.75rem;color:var(--ink-light)}
.empty-title{font-family:var(--serif);font-size:1.8rem;font-weight:300;font-style:italic}
.empty-sub{font-family:var(--mono);font-size:.75rem;letter-spacing:.08em}

/* Scrollbar */
::-webkit-scrollbar{width:3px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bg-3);border-radius:2px}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-logo">
    <div class="logo-dot"></div>
    blog editor
  </div>
  <div class="topbar-right">
    <span class="status" id="status">idle</span>
    <button class="btn btn-ghost" onclick="newPost()">+ New</button>
    <button class="btn btn-ghost" onclick="savePost()">Save <span style="opacity:.5;font-size:.65rem">Ctrl+S</span></button>
    <button class="btn btn-primary" onclick="publishAll()">Publish &rarr; GitHub</button>
  </div>
</div>

<div class="layout">

  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-head">
      <span class="sidebar-label">Posts</span>
    </div>
    <div class="post-list" id="post-list"></div>
  </aside>

  <!-- Editor -->
  <div class="editor-pane">

    <!-- Empty state -->
    <div class="empty" id="empty-state">
      <div class="empty-title">Nothing selected.</div>
      <div class="empty-sub">Click "+ New" or pick a post.</div>
    </div>

    <!-- Editor form (hidden until a post is selected/created) -->
    <div id="editor-form" style="display:none;flex:1;flex-direction:column;overflow:hidden">
      <div class="meta-bar">
        <input class="meta-input is-title" id="f-title" placeholder="Post title" type="text" autocomplete="off">
        <input class="meta-input"          id="f-date"  type="date">
        <input class="meta-input"          id="f-tags"  placeholder="tags, comma-separated" type="text" autocomplete="off">
      </div>
      <div class="toolbar">
        <button class="tb" onclick="fmt('**','**')" title="Bold"><b>B</b></button>
        <button class="tb" onclick="fmt('*','*')"   title="Italic"><i>I</i></button>
        <button class="tb" onclick="fmt('`','`')"   title="Code">code</button>
        <span class="tb-sep"></span>
        <button class="tb" onclick="line('# ')"   title="H1">H1</button>
        <button class="tb" onclick="line('## ')"  title="H2">H2</button>
        <button class="tb" onclick="line('### ')" title="H3">H3</button>
        <span class="tb-sep"></span>
        <button class="tb" onclick="line('- ')"  title="List item">list</button>
        <button class="tb" onclick="line('> ')"  title="Blockquote">quote</button>
        <button class="tb" onclick="codeBlock()" title="Code block">```</button>
        <button class="tb" onclick="line('---')" title="Divider">---</button>
        <span class="tb-sep"></span>
        <button class="tb" onclick="line('[text](url)')" title="Link">link</button>
        <div style="flex:1"></div>
        <button class="tb" id="tb-preview" onclick="togglePreview()" title="Toggle preview (Ctrl+P)">Preview</button>
        <span class="tb-sep"></span>
        <button class="tb btn-danger" onclick="deletePost()" title="Delete post">Delete</button>
      </div>
      <div class="editor-area">
        <div class="editor-wrap">
          <pre class="hl-pre" id="hl" aria-hidden="true"></pre>
          <textarea class="md-textarea" id="md" placeholder="Write in Markdown..."></textarea>
        </div>
        <div class="preview" id="preview"></div>
      </div>
    </div>

  </div>
</div>

<script>
let currentFile = null;
let showingPreview = false;

// ── Syntax highlighting ───────────────────────────────────────────────────────
function highlight(text) {
  const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const lines = esc(text).split('\n');
  let inCode = false;
  return lines.map(line => {
    if (/^```/.test(line)) { inCode = !inCode; return `<span class="hl-fence">${line}</span>`; }
    if (inCode) return `<span class="hl-cb">${line}</span>`;
    if (line === '---') return `<span class="hl-meta">${line}</span>`;
    if (/^#{1,6} /.test(line)) return `<span class="hl-h">${line}</span>`;
    if (/^&gt; /.test(line)) return `<span class="hl-bq">${line}</span>`;
    if (/^[-*] /.test(line) || /^\d+\. /.test(line)) return `<span class="hl-li">${line}</span>`;
    return line
      .replace(/(`[^`]+`)/g, '<span class="hl-ic">$1</span>')
      .replace(/(\*\*[^*\n]+\*\*)/g, '<span class="hl-bold">$1</span>')
      .replace(/(\*[^*\n]+\*)/g, '<span class="hl-em">$1</span>')
      .replace(/(\[[^\]]+\]\([^)]+\))/g, '<span class="hl-link">$1</span>');
  }).join('\n');
}

function syncHighlight() {
  const ta = document.getElementById('md');
  const hl = document.getElementById('hl');
  hl.innerHTML = highlight(ta.value) + '\n';
  hl.scrollTop = ta.scrollTop;
}

// ── Boot ──────────────────────────────────────────────────────────────────────
loadPosts();

// ── Load sidebar ──────────────────────────────────────────────────────────────
async function loadPosts() {
  const posts = await (await fetch('/api/posts')).json();
  const ul = document.getElementById('post-list');
  ul.innerHTML = '';
  posts.forEach(p => {
    const el = document.createElement('div');
    el.className = 'post-row' + (p.file === currentFile ? ' active' : '');
    el.innerHTML = `<div class="pr-title">${p.title}</div><div class="pr-date">${p.date || 'No date'}</div>`;
    el.onclick = () => openPost(p.file);
    ul.appendChild(el);
  });
}

// ── Open a post ───────────────────────────────────────────────────────────────
async function openPost(file) {
  currentFile = file;
  const data = await (await fetch(`/api/post?file=${encodeURIComponent(file)}`)).json();
  document.getElementById('f-title').value = data.meta.title || '';
  document.getElementById('f-date').value  = data.meta.date  || '';
  document.getElementById('f-tags').value  = data.meta.tags  || '';
  document.getElementById('md').value      = data.body       || '';
  showEditor();
  loadPosts();
  syncHighlight();
  if (showingPreview) renderPreview();
}

// ── New post ──────────────────────────────────────────────────────────────────
function newPost() {
  currentFile = null;
  document.getElementById('f-title').value = '';
  document.getElementById('f-date').value  = new Date().toISOString().slice(0, 10);
  document.getElementById('f-tags').value  = '';
  document.getElementById('md').value      = '';
  showEditor();
  syncHighlight();
  document.getElementById('f-title').focus();
}

// ── Save ──────────────────────────────────────────────────────────────────────
async function savePost() {
  const title = document.getElementById('f-title').value.trim() || 'Untitled';
  const date  = document.getElementById('f-date').value;
  const tags  = document.getElementById('f-tags').value;
  const body  = document.getElementById('md').value;
  setStatus('saving…', 'busy');
  const res  = await fetch('/api/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({file: currentFile, title, date, tags, body}),
  });
  const data = await res.json();
  currentFile = data.file;
  setStatus('saved', 'ok');
  setTimeout(() => setStatus('idle'), 2500);
  loadPosts();
}

// ── Delete ────────────────────────────────────────────────────────────────────
async function deletePost() {
  if (!currentFile) return;
  if (!confirm(`Delete this post? This cannot be undone.`)) return;
  await fetch(`/api/delete?file=${encodeURIComponent(currentFile)}`, {method: 'DELETE'});
  currentFile = null;
  showEmpty();
  loadPosts();
}

// ── Publish ───────────────────────────────────────────────────────────────────
async function publishAll() {
  setStatus('building…', 'busy');
  const res  = await fetch('/api/publish', {method: 'POST'});
  const data = await res.json();
  if (data.ok) {
    setStatus('published!', 'ok');
  } else {
    setStatus('error', 'error');
    alert('Git output:\n\n' + data.log);
  }
  setTimeout(() => setStatus('idle'), 5000);
}

// ── Toolbar helpers ───────────────────────────────────────────────────────────
function fmt(before, after) {
  const ta = document.getElementById('md');
  const s = ta.selectionStart, e = ta.selectionEnd;
  const sel = ta.value.slice(s, e) || 'text';
  const replacement = before + sel + after;
  ta.setRangeText(replacement, s, e, 'select');
  ta.focus();
}

function line(prefix) {
  const ta  = document.getElementById('md');
  const pos = ta.selectionStart;
  const nl  = ta.value[pos - 1] === '\n' || pos === 0 ? '' : '\n';
  ta.setRangeText(nl + prefix, pos, pos, 'end');
  ta.focus();
}

function codeBlock() {
  const ta  = document.getElementById('md');
  const pos = ta.selectionStart;
  ta.setRangeText('\n```\n\n```\n', pos, pos, 'end');
  ta.focus();
}

// ── Preview ───────────────────────────────────────────────────────────────────
function togglePreview() {
  showingPreview = !showingPreview;
  document.getElementById('preview').classList.toggle('show', showingPreview);
  document.getElementById('tb-preview').classList.toggle('on', showingPreview);
  if (showingPreview) renderPreview();
}

async function renderPreview() {
  const body = document.getElementById('md').value;
  const data = await (await fetch('/api/preview', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({body}),
  })).json();
  document.getElementById('preview').innerHTML = data.html;
}

document.getElementById('md').addEventListener('input', () => {
  syncHighlight();
  if (showingPreview) renderPreview();
});
document.getElementById('md').addEventListener('scroll', () => {
  document.getElementById('hl').scrollTop = document.getElementById('md').scrollTop;
});

// ── UI helpers ────────────────────────────────────────────────────────────────
function showEditor() {
  document.getElementById('empty-state').style.display = 'none';
  const f = document.getElementById('editor-form');
  f.style.display      = 'flex';
  f.style.flex         = '1';
  f.style.flexDirection = 'column';
  f.style.overflow     = 'hidden';
}

function showEmpty() {
  document.getElementById('empty-state').style.display = 'flex';
  document.getElementById('editor-form').style.display = 'none';
}

function setStatus(msg, cls = '') {
  const el = document.getElementById('status');
  el.textContent = msg;
  el.className   = 'status' + (cls ? ' ' + cls : '');
}

// ── Keyboard shortcuts ────────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); savePost(); }
  if ((e.ctrlKey || e.metaKey) && e.key === 'p') { e.preventDefault(); togglePreview(); }
});

// Tab key in textarea
document.getElementById('md').addEventListener('keydown', e => {
  if (e.key === 'Tab') {
    e.preventDefault();
    const ta = e.target;
    ta.setRangeText('    ', ta.selectionStart, ta.selectionEnd, 'end');
  }
});
</script>
</body>
</html>"""

# ── HTTP request handler ──────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Quiet console output

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    # ──────────────────────────────────────────────────────────────────────────
    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        qs     = parse_qs(parsed.query)

        if path == "/":
            self.send_html(EDITOR_HTML)

        elif path == "/api/posts":
            self.send_json(all_posts())

        elif path == "/api/post":
            fname = qs.get("file", [""])[0]
            md    = POSTS_DIR / fname
            if not md.exists():
                self.send_json({"error": "not found"}, 404); return
            meta, body = parse_post(md)
            self.send_json({"meta": meta, "body": body})

        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/save":
            d     = self.read_json()
            title = d.get("title", "Untitled").strip() or "Untitled"
            date  = d.get("date",  "")
            tags  = d.get("tags",  "")
            body  = d.get("body",  "")
            fname = d.get("file")

            if not fname:
                slug  = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
                fname = slug + ".md"
            if not fname.endswith(".md"):
                fname += ".md"

            content = f"---\ntitle: {title}\ndate: {date}\ntags: {tags}\n---\n\n{body}"
            (POSTS_DIR / fname).write_text(content, "utf-8")
            self.send_json({"ok": True, "file": fname})

        elif path == "/api/preview":
            d    = self.read_json()
            html = md_to_html(d.get("body", ""))
            self.send_json({"html": html})

        elif path == "/api/publish":
            ok, log = do_publish()
            self.send_json({"ok": ok, "log": log})

        else:
            self.send_response(404); self.end_headers()

    def do_DELETE(self):
        qs    = parse_qs(urlparse(self.path).query)
        fname = qs.get("file", [""])[0]
        md    = POSTS_DIR / fname
        if md.exists():
            md.unlink()
            html_out = BLOG_DIR / fname.replace(".md", ".html")
            if html_out.exists():
                html_out.unlink()
        self.send_json({"ok": True})


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Auto-build index on start so blog/index.html always exists
    posts = all_posts()
    (BLOG_DIR / "index.html").write_text(build_index_html(posts), "utf-8")

    md_available = True
    try:
        import markdown
    except ImportError:
        md_available = False

    print(f"\n  ┌─ Blog Editor ─────────────────────────────────")
    print(f"  │  Open: http://localhost:{PORT}")
    print(f"  │  Posts: {POSTS_DIR}")
    if not md_available:
        print(f"  │")
        print(f"  │  Tip: pip install markdown  (better rendering)")
    print(f"  └───────────────────────────────────────────────")
    print(f"  Ctrl+C to stop.\n")

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\n  Editor stopped.")
