#!/usr/bin/env python3
"""
Builds real, crawlable pages for every blog post in posts.json.

  blog/<number>/index.html one page per post  ->  https://rishit.fun/blog/<number>/
  sitemap.xml              home page + every post
  robots.txt               points crawlers at the sitemap

The pages reuse the look of index.html (its <style> block, background, nav),
so they always match the main site. Run it by hand with `python3 build_blog.py`,
or let the GitHub Action in .github/workflows/build-blog.yml run it whenever
posts.json changes (which is what happens when he publishes from the site).

Python standard library only.
"""
import html
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = "https://rishit.fun"
AUTHOR = "Rishit Srivastava"


# --------------------------------------------------------------------------
# Short numbered addresses: the oldest post is /blog/1/, the next /blog/2/, ...
# This logic is mirrored in index.html (slugMap) so the links in the blog list
# always point at the pages built here. Keep them in sync.
# --------------------------------------------------------------------------
def slug_map(posts):
    ordered = sorted(posts, key=lambda p: p.get("id") or 0)
    return {p.get("id"): str(i + 1) for i, p in enumerate(ordered)}


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def post_datetime(post):
    try:
        return datetime.fromtimestamp(int(post["id"]) / 1000, tz=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def describe(body, limit=155):
    flat = re.sub(r"\s+", " ", str(body or "")).strip()
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    cut = re.sub(r"\s+\S*$", "", cut)
    return cut + "…"


def grab(pattern, text, what):
    m = re.search(pattern, text, re.S)
    if not m:
        raise SystemExit(f"build_blog.py: could not find {what} in index.html")
    return m.group(1) if m.groups() else m.group(0)


# --------------------------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>@@TITLE@@ | @@AUTHOR@@</title>
  <meta name="description" content="@@DESC@@" />
  <meta name="author" content="@@AUTHOR@@" />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <meta name="theme-color" content="#06050e" />
  <link rel="canonical" href="@@URL@@" />

  <meta property="og:type" content="article" />
  <meta property="og:url" content="@@URL@@" />
  <meta property="og:title" content="@@TITLE@@" />
  <meta property="og:description" content="@@DESC@@" />
  <meta property="og:image" content="@@OGIMAGE@@" />
  <meta property="og:site_name" content="@@AUTHOR@@" />
  <meta property="article:published_time" content="@@ISO@@" />
  <meta property="article:author" content="@@AUTHOR@@" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="@@TITLE@@" />
  <meta name="twitter:description" content="@@DESC@@" />
  <meta name="twitter:image" content="@@OGIMAGE@@" />

  @@FAVICON@@
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  @@FONTS@@
  <script type="application/ld+json">@@JSONLD@@</script>
  <style>@@STYLE@@
    /* extras for standalone post pages */
    a.topnav-link { text-decoration: none; display: inline-block; }
    a.blog-back { text-decoration: none; }
    .pineapple-link { display: flex; align-items: center; padding: 2px; border-radius: 8px; transition: transform .14s; }
    .pineapple-link:hover { transform: scale(1.1); }
  </style>
</head>
<body>

  <div class="bg-gif"></div>
  <div class="bg-overlay"></div>

  <nav class="topnav" aria-label="Primary navigation">
    <div class="topnav-left">
      <a class="pineapple-link" href="/" aria-label="Home"><img src="@@PINEAPPLE@@" alt="pineapple" width="24" height="24" draggable="false" /></a>
      <div class="clock-wrap">
        <span class="clock-val" id="clockVal"></span>
        <span class="clock-greeting" id="clockGreeting"></span>
      </div>
    </div>
    <div class="topnav-links">
      <a class="topnav-link" href="/">about</a>
      <a class="topnav-link" href="/?page=projects">projects</a>
      <a class="topnav-link active" href="/?page=blogs">blogs</a>
    </div>
    <div class="topnav-right"></div>
  </nav>

  <main class="main-content">
    <article class="fade-in">
      <a class="blog-back" href="/?page=blogs">← back to blogs</a>
      <h1 class="blog-detail-title">@@TITLE@@</h1>
      <span class="blog-detail-date">@@DATE@@<span id="viewWrap"></span></span>
      <div class="blog-detail-body">@@BODY@@</div>
      @@IMAGES@@
      <div class="blog-detail-actions">
        <button class="share-btn" id="copyBtn" type="button">copy link</button>
      </div>
    </article>
  </main>

  <script>
    // Same inspection deterrents as the main page.
    document.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    document.addEventListener("keydown", function (event) {
      var modifier = event.ctrlKey || event.metaKey;
      var key = event.key.toLowerCase();
      var blocked =
        event.key === "F12" ||
        (modifier && event.shiftKey && ["i", "j", "c"].indexOf(key) !== -1) ||
        (modifier && key === "u");
      if (blocked) event.preventDefault();
    });

    (function () {
      var WORKER = "@@WORKER@@";
      var POST_ID = "@@ID@@";
      var PING_ENDPOINT = "@@PING@@";
      var CANONICAL = "@@URL@@";

      // Clock
      function updateClock() {
        var t = new Date().toLocaleTimeString("en-US", {
          timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
        });
        document.getElementById("clockVal").textContent = t;
        var h = parseInt(new Date().toLocaleString("en-US", { timeZone: "Asia/Kolkata", hour: "numeric", hour12: false }));
        var g = h >= 5 && h < 12 ? "Good morning ☀️"
              : h >= 12 && h < 17 ? "Good afternoon ☀️"
              : h >= 17 && h < 20 ? "Good evening 🌇"
              : "It's currently night 🌙";
        document.getElementById("clockGreeting").textContent = g;
      }
      updateClock();
      setInterval(updateClock, 1000);

      // View count: register once per tab, otherwise just show the current number
      function setViews(n) {
        var el = document.getElementById("viewWrap");
        if (el) el.textContent = " · " + n + " view" + (n === 1 ? "" : "s");
      }
      var key = "viewed:" + POST_ID, counted = false;
      try { counted = !!sessionStorage.getItem(key); } catch (e) {}
      if (!counted) {
        try { sessionStorage.setItem(key, "1"); } catch (e) {}
        fetch(WORKER + "/view?id=" + encodeURIComponent(POST_ID), { method: "POST" })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (d) { if (d && typeof d.count === "number") setViews(d.count); })
          .catch(function () {});
      } else {
        fetch(WORKER + "/views?t=" + Date.now(), { cache: "no-store" })
          .then(function (r) { return r.ok ? r.json() : {}; })
          .then(function (m) { setViews(m[POST_ID] || 0); })
          .catch(function () {});
      }

      // Visitor ping (once per tab), same as the main page
      try {
        if (!sessionStorage.getItem("visit_logged")) {
          sessionStorage.setItem("visit_logged", "1");
          fetch(PING_ENDPOINT, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ page: location.href, referrer: document.referrer, userAgent: navigator.userAgent })
          }).catch(function () {});
        }
      } catch (e) {}

      // Copy link
      document.getElementById("copyBtn").addEventListener("click", function () {
        var btn = this, original = btn.textContent;
        navigator.clipboard.writeText(CANONICAL).then(function () {
          btn.textContent = "copied!";
          setTimeout(function () { btn.textContent = original; }, 1500);
        }).catch(function () { window.prompt("Copy this link:", CANONICAL); });
      });

      // Image slideshow
      document.querySelectorAll(".blog-slideshow").forEach(function (el) {
        var images;
        try { images = JSON.parse(el.dataset.images); } catch (e) { images = []; }
        if (images.length <= 1) return;
        var idx = 0;
        var img = el.querySelector(".blog-image");
        var dots = el.querySelectorAll(".slideshow-dot");
        setInterval(function () {
          idx = (idx + 1) % images.length;
          img.style.opacity = "0";
          setTimeout(function () { img.src = images[idx]; img.style.opacity = "1"; }, 200);
          dots.forEach(function (d, i) { d.classList.toggle("active", i === idx); });
        }, 3000);
      });
    })();
  </script>
</body>
</html>
"""


# /blog/ on its own has no page, so send visitors to the blog list instead of a 404.
REDIRECT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Blogs | Rishit Srivastava</title>
  <meta name="robots" content="noindex" />
  <link rel="canonical" href="https://rishit.fun/" />
  <meta http-equiv="refresh" content="0; url=/?page=blogs" />
  <script>location.replace("/?page=blogs");</script>
</head>
<body><a href="/?page=blogs">Go to blogs</a></body>
</html>
"""


def build():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    posts_raw = json.loads((ROOT / "posts.json").read_text(encoding="utf-8"))
    posts = posts_raw if isinstance(posts_raw, list) else posts_raw.get("posts", [])

    style = grab(r"<style>(.*?)</style>", index, "the <style> block")
    worker = grab(r'const WORKER_BASE = "([^"]+)"', index, "WORKER_BASE")
    ping = grab(r'const PING_ENDPOINT = "([^"]+)"', index, "PING_ENDPOINT")
    og_image = grab(r'property="og:image" content="([^"]+)"', index, "og:image")
    favicon = grab(r'(<link rel="icon"[^>]*>)', index, "the favicon link")
    fonts = grab(r'(<link href="https://fonts\.googleapis\.com/css2[^>]*>)', index, "the fonts link")
    pineapple = grab(r'<img src="([^"]+)" alt="pineapple"', index, "the pineapple icon")

    slugs = slug_map(posts)

    blog_dir = ROOT / "blog"
    if blog_dir.exists():
        shutil.rmtree(blog_dir)

    blog_dir.mkdir(parents=True, exist_ok=True)
    (blog_dir / "index.html").write_text(REDIRECT, encoding="utf-8")

    sitemap = [f"  <url><loc>{SITE}/</loc></url>"]

    for p in sorted(posts, key=lambda p: p.get("id") or 0):
        slug = slugs[p.get("id")]
        url = f"{SITE}/blog/{slug}/"
        title = str(p.get("title") or "Untitled")
        body = str(p.get("body") or "")
        dt = post_datetime(p)
        iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        images = [str(i) for i in (p.get("images") or []) if i]

        if images:
            dots = ""
            if len(images) > 1:
                dots = '<div class="slideshow-dots">' + "".join(
                    f'<span class="slideshow-dot{" active" if i == 0 else ""}"></span>'
                    for i in range(len(images))
                ) + "</div>"
            images_html = (
                f'<div class="blog-slideshow" data-images="{esc(json.dumps(images))}">'
                f'<img class="blog-image" src="{esc(images[0])}" alt="{esc(title)}" '
                f"onerror=\"this.closest('.blog-slideshow').remove()\" />{dots}</div>"
            )
        else:
            images_html = ""

        jsonld = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": title,
            "description": describe(body),
            "datePublished": iso,
            "author": {"@type": "Person", "name": AUTHOR, "url": SITE + "/"},
            "mainEntityOfPage": url,
            "url": url,
        }
        if images:
            jsonld["image"] = images
        jsonld_text = json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")

        page = PAGE
        for key, value in {
            "@@TITLE@@": esc(title),
            "@@AUTHOR@@": esc(AUTHOR),
            "@@DESC@@": esc(describe(body)),
            "@@URL@@": url,
            "@@OGIMAGE@@": esc(og_image),
            "@@ISO@@": iso,
            "@@FAVICON@@": favicon,
            "@@FONTS@@": fonts,
            "@@JSONLD@@": jsonld_text,
            "@@PINEAPPLE@@": esc(pineapple),
            "@@DATE@@": esc(p.get("date") or ""),
            "@@BODY@@": esc(body),
            "@@IMAGES@@": images_html,
            "@@WORKER@@": worker,
            "@@PING@@": ping,
            "@@ID@@": esc(p.get("id")),
            "@@STYLE@@": style,
        }.items():
            page = page.replace(key, value)

        out = blog_dir / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        sitemap.append(f"  <url><loc>{url}</loc><lastmod>{dt.strftime('%Y-%m-%d')}</lastmod></url>")
        print("built", out.relative_to(ROOT))

    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(sitemap)
        + "\n</urlset>\n",
        encoding="utf-8",
    )
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8"
    )
    print(f"done: {len(posts)} post page(s), sitemap.xml, robots.txt")


if __name__ == "__main__":
    build()
