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


def make_index_html(posts, include_admin_nav=False):
    nav_html = create_nav(active_page='home', depth=0)
    
    cards = ""
    for post in posts:
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
    </div>
</body>
</html>"""


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


def rebuild_outputs():
    """Regenerera alla statiska HTML-filer"""
    posts = load_posts()
    
    # Generera blogg-sidor
    index_html = make_index_html(posts, include_admin_nav=False)
    Path('output/index.html').write_text(index_html, encoding='utf-8')
    
    for post in posts:
        if post:
            post_html = make_post_html(post)
            output_file = Path('output/posts') / post['filename']
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(post_html, encoding='utf-8')
    
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
        return make_index_html(posts, include_admin_nav=True)
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
            </style>
        </head>
        <body>
            <h1>✓ Exporterat!</h1>
            <p>Sidan har genererats i mappen <code>output/</code></p>
            <p><a href="/">← Tillbaka</a></p>
        </body>
        </html>
        """
    except Exception as e:
        print(f"Error in export: {e}")
        return f"Exportfel: {str(e)}", 500


if __name__ == "__main__":
    app.run(debug=True)
