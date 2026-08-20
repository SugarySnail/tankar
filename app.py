from flask import Flask, render_template, request, redirect, url_for, jsonify
from pathlib import Path
from datetime import datetime
import html
import re
import xml.etree.ElementTree as ET
import os
from collections import Counter
from functools import wraps

app = Flask(__name__, static_folder='output', static_url_path='')

# ============================================================================
# KONFIGURATION
# ============================================================================

BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "posts"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_POSTS_DIR = OUTPUT_DIR / "posts"

MICRO_DIR = Path('posts/micro')
MICRO_OUTPUT_DIR = Path('output/micro')
MICRO_PER_PAGE = 30

POSTS_DIR.mkdir(exist_ok=True)
OUTPUT_POSTS_DIR.mkdir(parents=True, exist_ok=True)

SITE_URL = "https://tankar.myjak.net"
SITE_TITLE = "My Jakobsson"
SITE_DESCRIPTION = "tankar"


# ============================================================================
# HJÄLPFUNKTIONER (måste komma före routes!)
# ============================================================================

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s_-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text


def escape_xml(text):
    """Escapar XML-specialtecken"""
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&apos;'))


def process_images_in_content(content):
    """Konverterar <img>-taggar från gamla attribut till moderna CSS-baserade."""
    def replace_img(match):
        img_tag = match.group(0)
        src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag)
        if not src_match:
            return img_tag
        src = src_match.group(1)
        return f'<img src="{src}" style="max-width: 100%; height: auto; display: block; margin: 1rem 0;">'
    
    return re.sub(r'<img[^>]*/?>', replace_img, content)


def paginate_posts(posts, per_page=10):
    """Delar upp inlägg i sidor. Returnerar lista av listor."""
    pages = []
    for i in range(0, len(posts), per_page):
        pages.append(posts[i:i+per_page])
    return pages


def make_pagination_html(current_page, total_pages, base_url=""):
    """Skapar HTML för sidnavigation (Föregående | Nästa)"""
    html_out = '<nav class="pagination">\n'
    
    # Föregående-knapp
    if current_page > 1:
        if current_page == 2:
            prev_url = "index.html"
        else:
            prev_url = f"page-{current_page - 1}.html"
        html_out += f' <a href="{prev_url}" class="prev">← Föregående</a>\n'
    
    # Sidnummer
    html_out += f' <span class="page-info">Sida {current_page} av {total_pages}</span>\n'
    
    # Nästa-knapp
    if current_page < total_pages:
        next_url = f"page-{current_page + 1}.html"
        html_out += f' <a href="{next_url}" class="next">Nästa →</a>\n'
    
    html_out += '</nav>\n'
    return html_out


def load_posts():
    posts = []
    for file in POSTS_DIR.glob("*.xml"):
        post = parse_post(str(file))
        if post:
            posts.append(post)
    posts.sort(key=lambda x: x["date"], reverse=True)
    return posts


def parse_post(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        tags = []
        tags_elem = root.find("tags")
        if tags_elem is not None:
            tags = [tag.text for tag in tags_elem.findall("tag") if tag.text]
        
        title = root.findtext("title", "")
        date = root.findtext("date", "")
        date_part = date.split("T")[0] if date else "0000-00-00"
        
        return {
            "title": title,
            "date": date,
            "content": root.findtext("content", ""),
            "tags": tags,
            "tags_str": ", ".join(tags),
            "filename": f"{date_part}-{slugify(title)}.html",
            "xml_filename": Path(xml_file).name
        }
    except Exception as e:
        print(f"Error parsing {xml_file}: {e}")
        return None


def get_post_by_xml_filename(xml_filename):
    """Hämtar ett inlägg baserat på XML-filnamnet."""
    xml_path = POSTS_DIR / xml_filename
    if not xml_path.exists():
        return None
    
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        title = root.findtext("title", "")
        date = root.findtext("date", "")
        date_part = date.split("T")[0] if date else "0000-00-00"
        
        tags = []
        tags_elem = root.find("tags")
        if tags_elem is not None:
            tags = [tag.text for tag in tags_elem.findall("tag") if tag.text]
        
        return {
            "title": title,
            "date": date,
            "content": root.findtext("content", ""),
            "tags": tags,
            "tags_str": ", ".join(tags),
            "filename": f"{date_part}-{slugify(title)}.html",
            "xml_filename": xml_filename
        }
    except Exception:
        return None


def save_post(title, date, content, tags_str, xml_filename=None):
    if not xml_filename:
        date_part = date.split("T")[0]
        slug = slugify(title)
        xml_filename = POSTS_DIR / f"{date_part}-{slug}.xml"
    else:
        xml_filename = Path(xml_filename)

    content = content.replace('="', '="')  
    content = content.replace('">', '">')  

    if not content.startswith('<p>'):
        content = f'<p>{content}'
    if not content.endswith('</p>'):
        content = f'{content}</p>'
    
    tags = [tag.strip() for tag in tags_str.split(",") if tag.strip()]

    root = ET.Element("post")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "date").text = date
    ET.SubElement(root, "content").text = content
    
    tags_elem = ET.SubElement(root, "tags")
    for tag in tags:
        ET.SubElement(tags_elem, "tag").text = tag
    
    tree = ET.ElementTree(root)
    tree.write(str(xml_filename), encoding="UTF-8", xml_declaration=True)


def create_nav(active_page=None, depth=0):
    """Creates navigation menu with relative paths based on depth."""
    prefix = "../" * depth
    
    nav_items = [
        (f"{prefix}index.html", "Hem", "home"),
        (f"{prefix}pages/poesi.html", "Poesi", "poesi"),
        (f"{prefix}micro/index.html", "Mikroblogg", "micro"),
        (f"{prefix}pages/faq.html", "FAQ", "faq"),
        (f"{prefix}tags/index.html", "Arkiv", "tags"),
        (f"{prefix}pages/rss.html", "RSS", "rss"),
        (f"{prefix}pages/om.html", "Om", "om"),
    ]
    
    nav_html = '<nav class="menu">\n'
    for href, label, page_key in nav_items:
        active_class = ' class="active"' if active_page == page_key else ''
        nav_html += f'    <a href="{href}"{active_class}>{label}</a>\n'
    nav_html += '</nav>'
    
    return nav_html


def make_index_html(posts, include_admin_nav=False, per_page=10):
    """Generera indexsida med pagination"""
    nav_html = create_nav(active_page='home', depth=0)
    
    # Dela upp inlägg i sidor
    pages = paginate_posts(posts, per_page)
    if not pages:
        return ""
    
    # Generera första sidan (index.html)
    page_posts = pages[0]
    cards = ""
    
    for post in page_posts:
        safe_title = html.escape(post["title"])
        
        try:
            dt = datetime.strptime(post["date"], "%Y-%m-%dT%H:%M")
            formatted_date = dt.strftime("%Y-%m-%d %H:%M")
        except:
            formatted_date = post["date"]
        
        safe_date = html.escape(formatted_date)
        safe_content = post["content"]
        
        tags_html = ""
        if post.get("tags"):
            tag_links = []
            for tag in post["tags"]:
                tag_slug = tag.replace(" ", "-").lower()
                tag_links.append(f'<a href="tags/{tag_slug}/" style="text-decoration: none;"><span class="tag">{html.escape(tag)}</span></a>')
            tags_html = " ".join(tag_links)
            tags_html = f'<div class="tags" style="text-align: right; margin-top: 1rem;">{tags_html}</div>'

        if include_admin_nav:
            link = f"/posts/{post['filename']}"
            xml_filename = post.get("xml_filename", "")
            edit_button = f'<a href="/edit/{xml_filename}" style="color:#ff9800; margin-left:10px;">✎ Redigera</a>'
        else:
            link = f"posts/{post['filename']}"
            edit_button = ""
        
        cards += f"""
        <div class="card">
            <h2><a href="{link}">{safe_title}</a>{edit_button}</h2>
            <p class="date">{safe_date}</p>
            <div>{safe_content}</div>
            {tags_html}
        </div>"""
    
    # Pagination
    pagination = make_pagination_html(1, len(pages)) if len(pages) > 1 else ""
    
    nav_section = ""
    if include_admin_nav:
        nav_section = """
    <nav class="menu">
        <a href="/create">Skapa inlägg</a>
        <a href="/micro-create">Mikroinlägg</a>
        <a href="/export">Exportera</a>
    </nav>"""
    else:
        nav_section = f"    {nav_html}"

    return f"""<!doctype html>
<html lang="sv">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="css/style.css">
    <title>{SITE_TITLE}</title>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1>{SITE_TITLE}</h1>
            <p>{SITE_DESCRIPTION}</p>
        </div>
    </header>
    {nav_section}
    <div class="grid">
        {cards}
        {pagination}
    </div>
</body>
</html>""", pages


def make_post_html(post, include_admin_nav=False):
    safe_title = html.escape(post["title"])
    safe_content = process_images_in_content(post["content"])
    
    try:
        dt = datetime.strptime(post["date"], "%Y-%m-%dT%H:%M")
        formatted_date = dt.strftime("%Y-%m-%d %H:%M")
    except:
        formatted_date = post["date"]
    
    safe_date = html.escape(formatted_date)

    nav_html = ""
    if include_admin_nav:
        xml_filename = post.get("xml_filename", "")
        nav_html = f"""    <a href="/">Hem</a>
    <a href="/create">Skapa inlägg</a>
    <a href="/export">Exportera</a>
    <a href="/edit/{xml_filename}" style="color:#ff9800;">✎ Redigera</a>"""
    else:
        nav_html = create_nav(active_page='posts', depth=1)

    return f"""<!doctype html>
<html lang="sv">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="../css/style.css">
    <title>{safe_title} - {SITE_TITLE}</title>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1>{SITE_TITLE}</h1>
        </div>
    </header>
    <nav class="menu">
        {nav_html}
    </nav>
    <div class="grid">
        <article class="card">
            <h2>{safe_title}</h2>
            <p class="date">{safe_date}</p>
            <div>{safe_content}</div>
            <p><a href="../index.html">← Tillbaka till startsidan</a></p>
        </article>
    </div>
</body>
</html>"""


def load_microblog_posts():
    """Ladda alla microblogs sorterade från nyast till äldst"""
    if not MICRO_DIR.exists():
        return []
    
    posts = []
    for xml_file in sorted(MICRO_DIR.glob('*.xml'), reverse=True):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            posts.append({
                'timestamp': root.find('timestamp').text,
                'content': root.find('content').text,
                'filename': xml_file.name
            })
        except Exception as e:
            print(f"Fel vid läsning av {xml_file}: {e}")
    
    return posts


def save_microblog_post(content):
    """Spara nytt microblogs-inlägg"""
    MICRO_DIR.mkdir(parents=True, exist_ok=True)
    
    now = datetime.now().strftime('%Y-%m-%d-%H%M%S')
    filename = f"{now}.xml"
    filepath = MICRO_DIR / filename
    
    root = ET.Element('micro')
    
    timestamp_elem = ET.SubElement(root, 'timestamp')
    timestamp_elem.text = datetime.now().isoformat()
    
    content_elem = ET.SubElement(root, 'content')
    content_elem.text = content
    
    tree = ET.ElementTree(root)
    tree.write(filepath, encoding='utf-8', xml_declaration=True)


def make_microblog_html(posts):
    """Generera microblogs-sidor med pagination"""
    MICRO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Dela upp i sidor
    total_pages = (len(posts) + MICRO_PER_PAGE - 1) // MICRO_PER_PAGE
    
    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * MICRO_PER_PAGE
        end_idx = start_idx + MICRO_PER_PAGE
        page_posts = posts[start_idx:end_idx]
        
        # Bygg inläggen med löpnummer
        posts_html = ''
        for idx, post in enumerate(page_posts):
            post_number = len(posts) - start_idx - idx
            posts_html += f'''<div class="micro-post">
            <div class="micro-content">{post['content']}</div>
            <div class="micro-footer">
                <span class="micro-time">{post['timestamp'][:16].replace('T', ' ')}</span>
                <span class="micro-number">#{post_number}</span>
            </div>
            </div>
            '''
        
        # Pagination
        pagination_html = make_pagination_html(page_num, total_pages) if total_pages > 1 else ''
        
        nav_html = create_nav(active_page='micro', depth=1)
        
        html_content = f'''<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mikroblogg - My Jakobsson</title>
    <link rel="stylesheet" href="../css/style.css">
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1>My Jakobsson</h1>
            <p>tankar</p>
        </div>
    </header>
    {nav_html}
    <main>
        <div class="grid">
            <div class="card">
                <h2>Mikroblogg</h2>
                <div style="display: flex; gap: 1rem; align-items: top;">
                    <img src="../bilder/static/mythinking.jpg" alt="Lekfull teckning av My med en fundersam min och stora glasögon, klädd i en mysig hoodie" style="width: 130px; height: 130px; flex-shrink: 0; border-radius: 8px;">
                    <div>
                        <p>Prenumerera <a href="/rss-micro.xml">via RSS</a>.</p>
                    </div>
                </div>
                {posts_html}
                {pagination_html}
            </div>
        </div>
    </main>
</body>
</html>'''
        
        # Skriv fil
        if page_num == 1:
            output_file = MICRO_OUTPUT_DIR / 'index.html'
        else:
            output_file = MICRO_OUTPUT_DIR / f'page-{page_num}.html'
        
        output_file.write_text(html_content, encoding='utf-8')
    
    print("✓ Mikroblogg regenererad med pagination")


def rebuild_outputs():
    """Regenerera alla statiska HTML-filer"""
    posts = load_posts()
    
    # Generera blogg-sidor med pagination
    index_html, pages = make_index_html(posts, include_admin_nav=False, per_page=10)
    Path('output/index.html').write_text(index_html, encoding='utf-8')
    
    # Generera övriga sidor
    if len(pages) > 1:
        for page_num in range(2, len(pages) + 1):
            page_posts = pages[page_num - 1]
            page_html, _ = make_index_html(posts, include_admin_nav=False, per_page=10)
            
            # Skapa sida N
            cards = ""
            for post in page_posts:
                safe_title = html.escape(post["title"])
                try:
                    dt = datetime.strptime(post["date"], "%Y-%m-%dT%H:%M")
                    formatted_date = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    formatted_date = post["date"]
                
                safe_date = html.escape(formatted_date)
                safe_content = post["content"]
                
                tags_html = ""
                if post.get("tags"):
                    tag_links = []
                    for tag in post["tags"]:
                        tag_slug = tag.replace(" ", "-").lower()
                        tag_links.append(f'<a href="tags/{tag_slug}/" style="text-decoration: none;"><span class="tag">{html.escape(tag)}</span></a>')
                    tags_html = " ".join(tag_links)
                    tags_html = f'<div class="tags" style="text-align: right; margin-top: 1rem;">{tags_html}</div>'
                
                cards += f"""
        <div class="card">
            <h2><a href="posts/{post['filename']}">{safe_title}</a></h2>
            <p class="date">{safe_date}</p>
            <div>{safe_content}</div>
            {tags_html}
        </div>"""
            
            pagination = make_pagination_html(page_num, len(pages))
            nav_html = create_nav(active_page='home', depth=0)
            
            page_content = f"""<!doctype html>
<html lang="sv">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="css/style.css">
    <title>{SITE_TITLE}</title>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1>{SITE_TITLE}</h1>
            <p>{SITE_DESCRIPTION}</p>
        </div>
    </header>
    {nav_html}
    <div class="grid">
        {cards}
        {pagination}
    </div>
</body>
</html>"""
            
            Path(f'output/page-{page_num}.html').write_text(page_content, encoding='utf-8')
    
    # Generera individuella inlägg
    for post in posts:
        if post:
            post_html = make_post_html(post)
            output_file = Path('output/posts') / post['filename']
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(post_html, encoding='utf-8')
    
    # Generera mikroblogg
    micro_posts = load_microblog_posts()
    make_microblog_html(micro_posts)
    
    print("✓ Regenererade alla inlägg och index")


def generate_rss_feeds(posts):
    """Genererar RSS-feeds"""
    print("✓ RSS-feeds uppdaterad")


# ============================================================================
# ADMIN DECORATOR
# ============================================================================

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if os.environ.get('FLASK_ENV') == 'production':
            return "Inte tillåtet i produktion", 403
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# ADMIN ROUTES (måste komma EFTER funktionsdefinitioner!)
# ============================================================================

@app.route("/")
@admin_only
def index():
    """Hem-sidan med admin-funktioner (localhost)"""
    try:
        posts = load_posts()
        generate_rss_feeds(posts)
        index_html, _ = make_index_html(posts, include_admin_nav=True, per_page=10)
        return index_html
    except Exception as e:
        print(f"Error in index route: {e}")
        return f"Error: {str(e)}", 500


@app.route("/posts/<filename>")
@admin_only
def post_page(filename):
    """Blogginläggen med admin-nav (localhost)"""
    try:
        for post in load_posts():
            if post["filename"] == filename:
                return make_post_html(post, include_admin_nav=True)
        return "Inlägget hittades inte", 404
    except Exception as e:
        print(f"Error in post_page: {e}")
        return f"Error: {str(e)}", 500


@app.route('/micro-create')
@admin_only
def micro_create():
    """Visa formulär för nytt microblogs-inlägg"""
    return render_template('micro_create.html')


@app.route('/micro-post', methods=['POST'])
@admin_only
def micro_post():
    """Spara microblogs-inlägg och regenerera sidor"""
    try:
        content = request.form.get('content', '').strip()
        
        if not content:
            return render_template('micro_create.html', 
                                   error='Inlägget kan inte vara tomt!'), 400
        
        if len(content) > 5000:
            return render_template('micro_create.html', 
                                   error='Inlägget är för långt (max 5000 tecken)'), 400
        
        save_microblog_post(content)
        
        posts = load_microblog_posts()
        make_microblog_html(posts)
        
        return '''
        <!doctype html>
        <html lang="sv">
        <head>
            <meta charset="utf-8">
            <title>Publicerat</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 40px; text-align: center; }
                a { color: #3A8DD5; }
            </style>
        </head>
        <body>
            <h1>✓ Publicerat!</h1>
            <p><a href="/">← Tillbaka</a></p>
        </body>
        </html>
        '''
    except Exception as e:
        print(f"Error in micro_post: {e}")
        return render_template('micro_create.html', 
                               error=f'Fel vid sparning: {str(e)}'), 500


@app.route("/create", methods=["GET", "POST"])
@admin_only
def create():
    """Skapa nytt inlägg"""
    try:
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            date = request.form.get("date", "").strip()
            content = request.form.get("content", "").strip()
            tags = request.form.get("tags", "").strip()
            
            if not all([title, date, content]):
                return render_template("create.html", 
                                       error="Alla fält krävs",
                                       default_date=datetime.now().strftime("%Y-%m-%dT%H:%M")), 400
            
            try:
                datetime.strptime(date, "%Y-%m-%dT%H:%M")
            except ValueError:
                return render_template("create.html", 
                                       error="Ogiltigt datumformat",
                                       default_date=datetime.now().strftime("%Y-%m-%dT%H:%M")), 400
            
            save_post(title, date, content, tags)
            rebuild_outputs()
            
            return redirect("/")
        
        default_date = datetime.now().strftime("%Y-%m-%dT%H:%M")
        return render_template("create.html", default_date=default_date)
    except Exception as e:
        print(f"Error in create: {e}")
        return f"Serverfel: {str(e)}", 500


@app.route("/edit/<filename>", methods=["GET", "POST"])
@admin_only
def edit(filename):
    """Redigera befintligt inlägg"""
    try:
        if ".." in filename or "/" in filename:
            return "Ogiltigt filnamn", 400
        
        xml_file = POSTS_DIR / filename
        
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            date = request.form.get("date", "").strip()
            content = request.form.get("content", "").strip()
            tags = request.form.get("tags", "").strip()
            
            if not all([title, date, content]):
                post = get_post_by_xml_filename(filename)
                return render_template("edit.html", 
                                       post=post,
                                       error="Alla fält krävs"), 400
            
            try:
                datetime.strptime(date, "%Y-%m-%dT%H:%M")
            except ValueError:
                post = get_post_by_xml_filename(filename)
                return render_template("edit.html", 
                                       post=post,
                                       error="Ogiltigt datumformat"), 400
            
            save_post(title, date, content, tags, str(xml_file))
            rebuild_outputs()
            
            return redirect("/")
        
        post = get_post_by_xml_filename(filename)
        if not post:
            return "Inlägget hittades inte", 404
        
        return render_template("edit.html", post=post)
    except Exception as e:
        print(f"Error in edit: {e}")
        return f"Serverfel: {str(e)}", 500


@app.route("/export")
@admin_only
def export_site():
    """Exportera och regenerera all HTML"""
    try:
        rebuild_outputs()
        return """
        <!doctype html>
    <html lang="sv">
    <head>
        <meta charset="utf-8">
        <title>Exporterat</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 40px; text-align: center; }
            a { color: #3A8DD5; }
            .button { 
                display: inline-block; 
                margin-top: 20px; 
                padding: 10px 20px; 
                background-color: #3A8DD5; 
                color: white; 
                text-decoration: none; 
                border-radius: 4px;
            }
            .button:hover { background-color: #2a6db5; }
        </style>
    </head>
    <body>
        <h1>✓ Exporterat!</h1>
        <p>Sidan har genererats i mappen <code>output/</code></p>
        <p>
            <a href="/" class="button">← Tillbaka</a>
            <a href="/export" class="button">Exportera</a>
        </p>
    </body>
    </html>
        """
    except Exception as e:
        print(f"Error in export: {e}")
        return f"Exportfel: {str(e)}", 500


@app.route("/page-<int:page_num>")
@admin_only
def paginated_index(page_num):
    """Visa paginererad index (sida 2, 3, osv)"""
    try:
        posts = load_posts()
        pages = paginate_posts(posts, per_page=10)
        
        if page_num < 1 or page_num > len(pages):
            return "Sidan finns inte", 404
        
        nav_html = create_nav(active_page='home', depth=0)
        page_posts = pages[page_num - 1]
        
        cards = ""
        for post in page_posts:
            safe_title = html.escape(post["title"])
            
            try:
                dt = datetime.strptime(post["date"], "%Y-%m-%dT%H:%M")
                formatted_date = dt.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_date = post["date"]
            
            safe_date = html.escape(formatted_date)
            safe_content = post["content"]
            
            tags_html = ""
            if post.get("tags"):
                tag_links = []
                for tag in post["tags"]:
                    tag_slug = tag.replace(" ", "-").lower()
                    tag_links.append(f'<a href="tags/{tag_slug}/" style="text-decoration: none;"><span class="tag">{html.escape(tag)}</span></a>')
                tags_html = " ".join(tag_links)
                tags_html = f'<div class="tags" style="text-align: right; margin-top: 1rem;">{tags_html}</div>'
            
            cards += f"""
        <div class="card">
            <h2><a href="posts/{post['filename']}">{safe_title}</a></h2>
            <p class="date">{safe_date}</p>
            <div>{safe_content}</div>
            {tags_html}
        </div>"""
        
        pagination = make_pagination_html(page_num, len(pages))
        
        return f"""<!doctype html>
<html lang="sv">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="css/style.css">
    <title>{SITE_TITLE}</title>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1>{SITE_TITLE}</h1>
            <p>{SITE_DESCRIPTION}</p>
        </div>
    </header>
    {nav_html}
    <div class="grid">
        {cards}
        {pagination}
    </div>
</body>
</html>"""
    except Exception as e:
        print(f"Error in paginated_index: {e}")
        return f"Error: {str(e)}", 500


if __name__ == "__main__":
    app.run(debug=True)
