import sqlite3
import html as html_mod
import re
from datetime import datetime
from pathlib import Path
import json

# ============================================================
# CONFIG
# ============================================================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "database_5menit" / "database.sqlite"
OUTPUT_DIR = BASE_DIR / "output"
BASE_URL = "https://thenewsday112.github.io/pyton"   # ✅ FIX: repo name

ARTICLES_PER_PAGE = 20
SITE_NAME = "News Portal Indonesia"

ADSTERRA_CODE = """
<div style="text-align:center;margin:20px 0;">
    <script type="text/javascript">
        atOptions = {
            'key' : 'f9e40eb3b3cd05f1038aac7b36b33ad2',
            'format' : 'iframe',
            'height' : 90,
            'width' : 728,
            'params' : {}
        };
    </script>
    <script type="text/javascript" src="https://upholdbrilliancerecast.com/f9e40eb3b3cd05f1038aac7b36b33ad2/invoke.js"></script>
</div>
"""

# ============================================================
# KAMUS KATEGORI
# ============================================================
CATEGORIES = [
    "technology", "business", "sports", "entertainment",
    "health", "science", "politics", "world",
    "finance", "travel", "food", "automotive",
    "education", "lifestyle", "other"
]

KEYWORDS = {
    "technology": ["teknologi", "tech", "ai", "artificial intelligence", "software", "digital", "internet", "komputer", "programming", "developer", "aplikasi", "sistem"],
    "business": ["bisnis", "business", "ekonomi", "finance", "saham", "investasi", "keuangan", "bank", "market", "funding", "ipo", "perusahaan"],
    "sports": ["olahraga", "sports", "sepakbola", "bola", "football", "soccer", "nba", "fifa", "liga", "pertandingan", "atlet", "motogp", "badminton"],
    "entertainment": ["hiburan", "entertainment", "film", "musik", "selebriti", "artis", "movie", "konser", "drama", "aktor"],
    "health": ["kesehatan", "health", "medis", "dokter", "rumah sakit", "obat", "penyakit", "virus", "vaksin"],
    "science": ["sains", "science", "penelitian", "nasa", "antariksa", "luar angkasa", "iklim", "lingkungan", "bumi"],
    "politics": ["politik", "politics", "pemerintah", "presiden", "menteri", "dpr", "pemilu", "partai"],
    "world": ["dunia", "world", "internasional", "global", "luar negeri"],
    "finance": ["keuangan", "finance", "uang", "kredit", "pinjaman", "pajak"],
    "travel": ["travel", "wisata", "liburan", "destinasi", "pariwisata", "hotel"],
    "food": ["makanan", "food", "kuliner", "resep", "restoran", "masakan"],
    "automotive": ["otomotif", "automotive", "mobil", "motor", "kendaraan", "mesin"],
    "education": ["pendidikan", "education", "sekolah", "kampus", "universitas", "belajar"],
    "lifestyle": ["gaya hidup", "lifestyle", "fashion", "kecantikan", "kesehatan mental"]
}

# ============================================================
# HELPER
# ============================================================
def esc(text):
    if not text:
        return ""
    return html_mod.escape(str(text))

def format_date(date_str):
    if not date_str:
        return "-"
    try:
        dt = datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
        return dt.strftime('%b %d, %Y')
    except Exception:
        return str(date_str)[:10]

def iso_date(date_str):
    """✅ FIX: paksa ISO 8601 untuk schema.org"""
    if not date_str:
        return datetime.now().isoformat()
    try:
        return datetime.fromisoformat(str(date_str).replace('Z', '+00:00')).isoformat()
    except Exception:
        return datetime.now().isoformat()

def detect_kategori(text):
    lower = text.lower()
    for cat, kws in KEYWORDS.items():
        if any(re.search(r'\b' + re.escape(kw) + r'\b', lower) for kw in kws):
            return cat
    return "other"

def ensure_database():
    """✅ FIX: buat DB kosong jika tidak ada, TIDAK exit(1)"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        return
    print(f"⚠️ WARNING: Database tidak ditemukan di {DB_PATH}")
    print("   Membuat database kosong agar workflow tetap jalan...")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS artikel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE, title TEXT, content TEXT, gambar TEXT,
            kategori TEXT DEFAULT 'other',
            tanggal_publish TEXT, tanggal_update TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("   ✅ Database kosong dibuat.\n")

def fix_database():
    print("[STEP 1] Checking database structure...")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS artikel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE,
            title TEXT,
            content TEXT,
            gambar TEXT,
            kategori TEXT DEFAULT 'other',
            tanggal_publish TEXT,
            tanggal_update TEXT
        )
    """)

    c.execute("PRAGMA table_info(artikel)")
    cols = {row[1] for row in c.fetchall()}

    renames = {"judul": "title", "konten": "content"}
    for old, new in renames.items():
        if old in cols and new not in cols:
            c.execute(f"ALTER TABLE artikel RENAME COLUMN {old} TO {new}")
            cols.discard(old)
            cols.add(new)

    required = {
        "gambar": "TEXT", "kategori": "TEXT DEFAULT 'other'",
        "tanggal_publish": "TEXT", "tanggal_update": "TEXT",
    }
    for col, col_type in required.items():
        if col not in cols:
            c.execute(f"ALTER TABLE artikel ADD COLUMN {col} {col_type}")

    c.execute("UPDATE artikel SET kategori = 'other' WHERE kategori IS NULL OR kategori = ''")
    conn.commit()

    c.execute("SELECT id, title, content, kategori FROM artikel")
    rows = c.fetchall()
    updated = 0
    for row in rows:
        artikel_id, title, content, current_cat = row
        if current_cat == "other":
            new_cat = detect_kategori(str(title) + " " + str(content))
            if new_cat != "other":
                c.execute("UPDATE artikel SET kategori = ? WHERE id = ?", (new_cat, artikel_id))
                updated += 1
    conn.commit()
    conn.close()
    print("   Database OK.\n")

# ============================================================
# HTML TEMPLATE
# ============================================================
HTML_HEAD = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="index, follow, max-image-preview:large">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary_large_image">
<style>
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#f4f6f8;margin:0;padding:20px;color:#333;line-height:1.6}}
.container{{max-width:1000px;margin:0 auto}}
header{{background:#1e293b;color:#fff;padding:20px;border-radius:12px;margin-bottom:20px;text-align:center;box-shadow:0 4px 6px rgba(0,0,0,.1)}}
header h1{{margin:0;font-size:26px;letter-spacing:1px}}
nav{{background:#fff;padding:10px;border-radius:12px;margin-bottom:24px;display:flex;gap:8px;flex-wrap:wrap;justify-content:center;box-shadow:0 2px 4px rgba(0,0,0,.05)}}
nav a{{padding:8px 16px;border-radius:8px;color:#475569;text-decoration:none;font-weight:600;transition:all .2s;font-size:14px}}
nav a:hover,nav a.active{{background:#2563eb;color:#fff}}
.article-card{{background:#fff;padding:24px;margin-bottom:24px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);border-left:4px solid #2563eb}}
.article-card h2{{margin:0 0 12px;font-size:22px;color:#1e293b}}
.article-meta{{font-size:13px;color:#64748b;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #e2e8f0}}
.article-meta a{{color:#2563eb;text-decoration:none;font-weight:bold}}
.article-body{{font-size:16px;line-height:1.8;color:#334155}}
.article-body img{{max-width:100%;height:auto;border-radius:8px;margin:16px 0}}
.pagination{{text-align:center;margin:40px 0;display:flex;flex-wrap:wrap;justify-content:center;gap:8px}}
.pagination a{{display:inline-block;padding:10px 16px;border-radius:8px;text-decoration:none;color:#334155;font-weight:bold;background:#fff;box-shadow:0 2px 4px rgba(0,0,0,.05);transition:all .2s}}
.pagination a:hover{{background:#f1f5f9}}
.pagination a.active{{background:#2563eb;color:#fff}}
footer{{text-align:center;color:#64748b;font-size:14px;padding:30px 0;border-top:1px solid #e2e8f0;margin-top:20px}}
</style>
</head>
<body>
<div class="container">
<header><h1>{site}</h1></header>
{nav}
"""

HTML_FOOT = """<footer>&copy; {year} {site}. All rights reserved.</footer>
</div></body></html>"""


def render_nav(active_cat, available_categories):
    html = '<nav>'
    a_all = ' class="active"' if active_cat == "" else ''
    html += f'<a href="index.html"{a_all}>🏠 All News</a>'
    for cat in CATEGORIES:
        if cat in available_categories and cat != "other":
            a_cat = ' class="active"' if active_cat == cat else ''
            html += f'<a href="{cat}.html"{a_cat}>📰 {cat.title()}</a>'
    if "other" in available_categories:
        a_other = ' class="active"' if active_cat == "other" else ''
        html += f'<a href="other.html"{a_other}>📰 Other</a>'
    return html + '</nav>'


def render_card(row, filename="index.html"):
    """✅ FIX: akses kolom aman, content di-escape, iklan tidak per kartu"""
    keys = row.keys()
    title    = row["title"]    if "title"    in keys else "No Title"
    content  = row["content"]  if "content"  in keys else ""
    gambar   = row["gambar"]   if "gambar"   in keys else ""
    kategori = row["kategori"] if "kategori" in keys else "other"
    link     = row["link"]     if "link"     in keys else "#"
    tanggal  = row["tanggal_publish"] if "tanggal_publish" in keys else ""
    aid      = row["id"]       if "id"       in keys else ""

    img = f'<img src="{esc(gambar)}" alt="{esc(title)}" loading="lazy">' if gambar else ""
    cat_label = kategori.title() if kategori else "Other"

    # ✅ Content di-escape agar aman dari XSS & layout rusak
    content_html = f"<p>{esc(content)}</p>" if content else ""

    schema_json = json.dumps({
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": title,
        "image": [gambar] if gambar else [],
        "datePublished": iso_date(tanggal),
        "dateModified": iso_date(tanggal),
        "mainEntityOfPage": f"{BASE_URL}/{filename}#artikel-{aid}"
    }, ensure_ascii=False)

    return f"""
<article class="article-card" id="artikel-{aid}">
    <script type="application/ld+json">{schema_json}</script>
    <h2>{esc(title)}</h2>
    <div class="article-meta">
        📅 {format_date(tanggal)} &nbsp;|&nbsp; Category: <strong>{esc(cat_label)}</strong> &nbsp;|&nbsp;
        <a href="{esc(link)}" target="_blank" rel="nofollow noopener">Read Source &rarr;</a>
    </div>
    <div class="article-body">{img}{content_html}</div>
</article>"""


def render_page(title, desc, canonical, rows, active_cat, available_categories, page_nav="", filename="index.html"):
    # ✅ FIX: iklan disisipkan setiap 5 artikel, bukan tiap kartu
    cards = ""
    for i, r in enumerate(rows):
        cards += render_card(r, filename)
        if (i + 1) % 5 == 0:
            cards += ADSTERRA_CODE

    head = HTML_HEAD.format(
        title=esc(title), desc=esc(desc), canonical=esc(canonical),
        site=esc(SITE_NAME), nav=render_nav(active_cat, available_categories)
    )
    body = f'<h1 style="color:#1e293b;border-left:5px solid #2563eb;padding-left:15px;margin-bottom:30px;">{esc(title)}</h1>'
    body += cards + page_nav
    return head + body + HTML_FOOT.format(year=datetime.now().year, site=esc(SITE_NAME))


def build_pagination(current, total, base_name):
    """✅ FIX: helper pagination untuk index & kategori"""
    if total <= 1:
        return ""
    nav = '<div class="pagination">'
    for j in range(1, total + 1):
        if base_name == "index":
            href = "index.html" if j == 1 else f"page{j}.html"
        else:
            href = f"{base_name}.html" if j == 1 else f"{base_name}-page{j}.html"
        a = ' class="active"' if j == current else ''
        nav += f'<a href="{href}"{a}>{j}</a>'
    nav += '</div>'
    return nav


# ============================================================
# EXPORT LOGIC
# ============================================================
def export_all():
    print("[STEP 2] Exporting HTML...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT DISTINCT kategori FROM artikel WHERE kategori IS NOT NULL")
    available_categories = list({(r[0] or "other").strip().lower() for r in c.fetchall()})

    c.execute("SELECT * FROM artikel ORDER BY tanggal_publish DESC, id DESC")
    all_rows = c.fetchall()
    total = len(all_rows)
    print(f"   Total articles: {total}")

    # --- Pagination utama ---
    if total > 0:
        pages = [all_rows[i:i+ARTICLES_PER_PAGE] for i in range(0, total, ARTICLES_PER_PAGE)]
        for i, page_rows in enumerate(pages, start=1):
            if i == 1:
                fn, canon, title = "index.html", f"{BASE_URL}/", f"{SITE_NAME} - Latest News"
            else:
                fn, canon, title = f"page{i}.html", f"{BASE_URL}/page{i}.html", f"{SITE_NAME} - Page {i}"

            nav = build_pagination(i, len(pages), "index")
            html = render_page(title, f"Page {i}", canon, page_rows, "", available_categories, nav, filename=fn)
            (OUTPUT_DIR / fn).write_text(html, encoding="utf-8")

    # --- Per kategori dengan pagination ---
    for cat in available_categories:
        c.execute("SELECT * FROM artikel WHERE kategori = ? ORDER BY tanggal_publish DESC", (cat,))
        rows = c.fetchall()
        if not rows:
            continue

        cat_pages = [rows[i:i+ARTICLES_PER_PAGE] for i in range(0, len(rows), ARTICLES_PER_PAGE)]
        for i, page_rows in enumerate(cat_pages, start=1):
            if i == 1:
                fn, canon, title = f"{cat}.html", f"{BASE_URL}/{cat}.html", f"{cat.title()} - {SITE_NAME}"
            else:
                fn = f"{cat}-page{i}.html"
                canon = f"{BASE_URL}/{fn}"
                title = f"{cat.title()} - {SITE_NAME} (Page {i})"

            nav = build_pagination(i, len(cat_pages), cat)
            html = render_page(title, f"Latest {cat} news", canon, page_rows, cat, available_categories, nav, filename=fn)
            (OUTPUT_DIR / fn).write_text(html, encoding="utf-8")
        print(f"   ✅ {cat}.html ({len(rows)} articles, {len(cat_pages)} pages)")

    # --- Sitemap ---
    today = datetime.now().strftime('%Y-%m-%d')
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    pages_count = max(1, (total + ARTICLES_PER_PAGE - 1) // ARTICLES_PER_PAGE)
    for i in range(1, pages_count + 1):
        url = f"{BASE_URL}/" if i == 1 else f"{BASE_URL}/page{i}.html"
        xml.append(f'<url><loc>{url}</loc><lastmod>{today}</lastmod><priority>1.0</priority></url>')

    for cat in available_categories:
        c.execute("SELECT COUNT(*) FROM artikel WHERE kategori = ?", (cat,))
        cnt = c.fetchone()[0]
        cat_pages_count = max(1, (cnt + ARTICLES_PER_PAGE - 1) // ARTICLES_PER_PAGE)
        for i in range(1, cat_pages_count + 1):
            fn = f"{cat}.html" if i == 1 else f"{cat}-page{i}.html"
            xml.append(f'<url><loc>{BASE_URL}/{fn}</loc><lastmod>{today}</lastmod><priority>0.9</priority></url>')

    xml.append('</urlset>')
    (OUTPUT_DIR / "sitemap.xml").write_text("\n".join(xml), encoding="utf-8")
    (OUTPUT_DIR / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf-8"
    )
    print(f"   ✅ sitemap.xml & robots.txt")

    conn.close()


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("EXPORT HTML (SEO Optimized)")
    print("=" * 55)
    print(f"Database: {DB_PATH}")
    print(f"Output:   {OUTPUT_DIR}\n")

    # ✅ FIX: jangan exit(1) — buat DB kosong jika tidak ada
    ensure_database()
    fix_database()
    export_all()

    print("\n" + "=" * 55)
    print("EXPORT COMPLETE!")
    print(f"Files are ready in: {OUTPUT_DIR}")
    print("=" * 55)
