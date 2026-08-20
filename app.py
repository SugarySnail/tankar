# ============================================================================
# GUIDE: Lägga till en ny statisk sida
# ============================================================================
# Följ dessa steg för att lägga till en ny sida (t.ex. /pages/exempel.html):
#
# STEG 1: Skapa funktionen make_{page}_html()
# ─────────────────────────────────────────────────────────────────────────
# Placera denna funktion tillsammans med andra make_*_html() funktioner:
#
#   def make_exempel_html():
#       """Generate the exempel page at output/pages/exempel.html."""
#   nav_html = create_nav(active_page='exempel', depth=1)
#       html_content = f"""<!DOCTYPE html>
#   <html lang="sv">
#   <head>
#       <meta charset="UTF-8">
#       <meta name="viewport" content="width=device-width, initial-scale=1.0">
#       <title>Exempel | My Jakobsson</title>
#       <link rel="stylesheet" href="../css/style.css">
#   </head>
#   <body>
#       <header class="header">
#           <div class="header-content">
#               <h1>My Jakobsson</h1>
#               <p>tankar</p>
#           </div>
#       </header>
#       {nav_html}
#       <main>
#        <div class="grid">      
#            <div class="card">
#               <h2>Exempel</h2>
#               <p>Ditt innehåll här...</p>
#           </div>
#          </div>
#       </main>
#   </body>
#   </html>"""
#       output_dir = Path('output/pages')
#       output_dir.mkdir(parents=True, exist_ok=True)
#       (output_dir / 'exempel.html').write_text(html_content, encoding='utf-8')
#
# STEG 2: Uppdatera create_nav() för att lägga till länken
# ─────────────────────────────────────────────────────────────────────────
# Lägg till denna rad i create_nav() innan </nav>:
#
#       <a href="/pages/exempel.html" class="{'active' if active_page == 'exempel' else ''}">Exempel</a>
#
# STEG 3: Anropa funktionen i rebuild_outputs()
# ─────────────────────────────────────────────────────────────────────────
# Lägg till denna rad tillsammans med andra make_*_html() anrop:
#
#       make_exempel_html()
#
# ============================================================================


from flask import Flask, render_template, request, redirect, url_for, jsonify
from pathlib import Path
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
import html
import re
import xml.etree.ElementTree as ET
import os
from collections import Counter


app = Flask(__name__, static_folder='output', static_url_path='')


BASE_DIR = Path(__file__).parent
POSTS_DIR = BASE_DIR / "posts"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_POSTS_DIR = OUTPUT_DIR / "posts"

# Mikroblogg
MICRO_DIR = Path('posts/micro')
MICRO_OUTPUT_DIR = Path('output/micro')
MICRO_PER_PAGE = 30

POSTS_DIR.mkdir(exist_ok=True)
OUTPUT_POSTS_DIR.mkdir(parents=True, exist_ok=True)

SITE_URL = "https://tankar.myjak.net"
SITE_TITLE = "My Jakobsson"
SITE_DESCRIPTION = "tankar"


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s_-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text

def process_images_in_content(content):
    """
    Konverterar <img>-taggar från gamla attribut till moderna CSS-baserade.
    Gör bilder responsiva och använder vettig bredd för sidan.
    """
    def replace_img(match):
        img_tag = match.group(0)
        
        # Extrahera src
        src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag)
        if not src_match:
            return img_tag  # Ingen src — behåll ursprunglig
        
        src = src_match.group(1)
        
        # Bygg ny <img> med CSS
        return f'<img src="{src}" style="max-width: 100%; height: auto; display: block; margin: 1rem 0;">'
    
    # Matcha alla <img ...> taggar
    return re.sub(r'<img[^>]*/?>', replace_img, content)

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

def load_posts():
    posts = []
    for file in POSTS_DIR.glob("*.xml"):
        post = parse_post(str(file))
        if post:
            posts.append(post)
    posts.sort(key=lambda x: x["date"], reverse=True)
    return posts

from datetime import datetime

def parse_post(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        tags = []
        tags_elem = root.find("tags")
        if tags_elem is not None:
            tags = [tag.text for tag in tags_elem.findall("tag") if tag.text]
        
        title = root.findtext("title", "")
        date_str = root.findtext("date", "")
        
        # Konvertera datum-sträng till datetime-objekt
        try:
            date_obj = datetime.fromisoformat(date_str) if date_str else datetime(1900, 1, 1)
        except ValueError:
            date_obj = datetime(1900, 1, 1)
        
        date_part = date_obj.strftime("%Y-%m-%d")
        filename = f"{date_part}-{slugify(title)}.html"
        
        return {
            "title": title,
            "date": date_obj,
            "content": root.findtext("content", ""),
            "tags": tags,
            "tags_str": ", ".join(tags),
            "filename": filename,
            "url": f"/{filename}",
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
        date_str = root.findtext("date", "")
        
        # Konvertera datum-sträng till datetime-objekt
        try:
            date = datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            date = datetime(1900, 1, 1)
        
        date_part = date.strftime("%Y-%m-%d")
        
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




def make_post_html(post, include_admin_nav=False):
    safe_title = html.escape(post["title"])
    safe_content = process_images_in_content(post["content"])
    
    # post["date"] är redan ett datetime-objekt, så formatera direkt
    formatted_date = post["date"].strftime("%Y-%m-%d %H:%M")
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




def paginate_posts(posts, per_page=10):
    """Delar upp inlägg i sidor. Returnerar lista av listor."""
    pages = []
    for i in range(0, len(posts), per_page):
        pages.append(posts[i:i+per_page])
    return pages

def make_pagination_html(current_page, total_pages, base_url="/"):
    """Skapar HTML för sidnavigation (Föregående | Nästa)"""
    html = '<nav class="pagination">\n'
    
    # Föregående-knapp
    if current_page > 1:
        if current_page == 2:
            prev_url = base_url
        else:
            prev_url = f"{base_url}page-{current_page - 1}.html"
        html += f'  <a href="{prev_url}" class="prev">← Föregående</a>\n'
    
    # Sidnummer
    html += f'  <span class="page-info">Sida {current_page} av {total_pages}</span>\n'
    
    # Nästa-knapp
    if current_page < total_pages:
        next_url = f"{base_url}page-{current_page + 1}.html"
        html += f'  <a href="{next_url}" class="next">Nästa →</a>\n'
    
    html += '</nav>\n'
    return html

def make_paginated_index_html(all_posts, posts_per_page=10):
    """Genererar alla indexsidor med paginering"""
    pages = paginate_posts(all_posts, posts_per_page)
    total_pages = len(pages)
    
    for page_num, page_posts in enumerate(pages, 1):
        # Bestäm filnamn
        if page_num == 1:
            filename = "index.html"
        else:
            filename = f"page-{page_num}.html"
        filepath = OUTPUT_DIR / filename
        
        # Bygga inlägg-kortet
        cards = ""
        for post in page_posts:
            safe_title = html.escape(post["title"])
            safe_date = post["date"].strftime("%Y-%m-%d")
            safe_content = post["content"]
            
            # Skapa taginformation
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
        
        # Lägg till paginering
        pagination_html = make_pagination_html(page_num, total_pages, base_url="/")
        
        # Generera full HTML-sidan
        nav_html = create_nav(active_page='home', depth=0)
        html_content = f"""<!doctype html>
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
</div>
{pagination_html}
</body>
</html>"""
        
        # Skriv fil
        filepath.write_text(html_content, encoding='utf-8')
        print(f"✓ Genererade {filename}")





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
           post_number = len(posts) - start_idx - idx  # Räkna från högsta nummer
           posts_html += f'''<div class="micro-post">
           <div class="micro-content">{post['content']}</div>
             <div class="micro-footer">
             <span class="micro-time">{post['timestamp'][:16].replace('T', ' ')}</span>
                <span class="micro-number">#{post_number}</span>
               </div>
                </div>
                '''
        
        # Pagination
        pagination_html = ''
        if total_pages > 1:
            pagination_html = '<div class="pagination">'
            if page_num > 1:
                if page_num == 2:
                    pagination_html += '<a href="../micro/">← Nyare</a>'
                else:
                    pagination_html += f'<a href="./page-{page_num - 1}.html">← Nyare</a>'
            
            pagination_html += f' <span>Sida {page_num}/{total_pages}</span> '
            
            if page_num < total_pages:
                pagination_html += f'<a href="./page-{page_num + 1}.html">Äldre →</a>'
            
            pagination_html += '</div>'
        
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
                    <img src="../bilder/static/mythinking.jpg" alt="Lekfull teckning av My med en fundersam min och stora glasögon, klädd i en mysig hoodie" style="width: 130px; height: 130px; flex-shrink: 0;">
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
    
    # Generera RSS-feed för mikrobloggen (efter alla sidor är skrivna)
    create_microblog_rss_file(posts)







def make_poesi_html():
       """Generate the page at output/pages/poesi.html."""
       nav_html = create_nav(active_page='poesi', depth=1)
       html_content = f"""<!DOCTYPE html>
   <html lang="sv">
   <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>Poesi | My Jakobsson</title>
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
               <h2>Poesi</h2>
               <p>Min fullständiga samling med poesi finns på <a href="https://poesi.myjak.net">https://poesi.myjak.net</a>.</p>
<p>Endast ny poesi läggs ut här i bloggen, i syfte att det ska gå att prenumerera på den <a href="https://tankar.myjak.net/rss-poesi.xml">via RSS</a> (<a href="rss.html">info</a>). Eventuella korrigeringar och omarbetningar av mina dikter publiceras enbart på <a href="https://poesi.myjak.net">https://poesi.myjak.net</a>, så om du vill citera mig, använd helst den sidan som källa för att säkerställa att du har den senaste versionen av dikten.</p><p>Tack!</p>
           </div>
          </div>
       </main>
   </body>
   </html>"""
       output_dir = Path('output/pages')
       output_dir.mkdir(parents=True, exist_ok=True)
       (output_dir / 'poesi.html').write_text(html_content, encoding='utf-8')

def make_om_html():
       """Generate the page at output/pages/om.html."""
       nav_html = create_nav(active_page='om', depth=1)
       html_content = f"""<!DOCTYPE html>
   <html lang="sv">
   <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>Kontakt | My Jakobsson</title>
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
               <h2>Kontakt</h2>
               <p>E-post: <a href="mailto:kontakt@myjak.net">kontakt@myjak.net</a></p>

                <h2>Om webbplatsen</h2>
                <p>Webbplatsen är byggd i samarbete med Claude Haiku 4.5 AI. Designvalet handlar om en romantisering av Mys svunna ungdom, då internet var ungt, oskuldsfullt och fyllt av möjligheter. Tecknade bilden överst i mikrobloggen är genererad av GPT 5.4 AI. </p><p>Allt övrigt innehåll i form av text och bild kommer ifrån My. Copyright råder, men det förstår ni. Ni är vuxna människor!
           </div>
          </div>
       </main>
   </body>
   </html>"""
       output_dir = Path('output/pages')
       output_dir.mkdir(parents=True, exist_ok=True)
       (output_dir / 'om.html').write_text(html_content, encoding='utf-8')

def make_faq_html():
    """Generate the FAQ page."""
    nav_html = create_nav(active_page='faq', depth=1)
    faq_content = (Path('templates') / 'faq.html').read_text(encoding='utf-8')
    
    html_content = f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FAQ – My Jakobsson</title>
    <link rel="stylesheet" href="../css/style.css">
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
        <div class="card">
            {faq_content}
        </div>
    </div>
</body>
</html>"""
    
    output_file = Path('output') / 'pages' / 'faq.html'
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html_content, encoding='utf-8')



def make_rss_page_html(posts):
    """Generate the RSS page at output/pages/rss.html with links to all feeds."""
    nav_html = create_nav(active_page='rss', depth=1)
    
    # Collect all tags and sort by frequency
    all_tags = {}
    for post in posts:
        for tag in post.get('tags', []):
            if tag not in all_tags:
                all_tags[tag] = 0
            all_tags[tag] += 1
    
    sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
    
    # Build tag feed links
    tag_feeds = ""
    for tag, count in sorted_tags:
        tag_slug = slugify(tag)
        tag_feeds += f'        <li><a href="/rss-{tag_slug}.xml">{tag}</a> ({count})</li>\n'
    
    html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RSS - My Jakobsson</title>
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

    <div class="grid">
        
        <div class="card">
        <h2>RSS-flöden</h2>
        
        <p>RSS är ett sätt att prenumerera på uppdateringar från mig. Du behöver en RSS-läsare (såsom Feedly, Microsoft Outlook, eller Thunderbird) för att läsa flödena. Att prenumerera är gratis, och jag kan inte spåra vem som prenumerar.</p>

        <h3>Huvudflöde</h3>
        <ul>
            <li><a href="/rss.xml">Alla inlägg</a> (utom mikrobloggen)</li>
        </ul>

        <h3>Flöden per tagg</h3>
        <ul>
        {tag_feeds}        </ul>

        <h3>Mikrobloggen</h3>
        <ul>
        <a href="/rss-micro.xml">Mikroblogg</a>        </ul>

        <h3>Hur prenumererar jag?</h3>
        <ol>
            <li>Installera en RSS-läsare</li>
            <li>Kopiera länken till ett flöde ovan</li>
            <li>Lägg till det i din RSS-läsare</li>
            <li>Du får då automatiska uppdateringar när nya inlägg publiceras</li>
        </ol>
    </div></div>
</body>
</html>"""
    
    output_file = Path('output') / 'pages' / 'rss.html'
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html, encoding='utf-8')



def make_tag_index_html(post, tag, posts):
    """Generates an HTML index page for a specific tag."""
    nav_html = create_nav(active_page='tags', depth=2)
    
    tag_posts = [p for p in posts if tag in p.get("tags", [])]
    
    if not tag_posts:
        return
    
    tag_posts.sort(key=lambda p: p["date"], reverse=True)
    
    posts_html = ""
    for p in tag_posts:
        safe_title = html.escape(p["title"])
        safe_content = p["content"]
        
        posts_html += f"""
    <article class="card">
        <h2><a href="../../posts/{p['filename']}">{safe_title}</a></h2>
        <p class="date">{p['date'].strftime("%Y-%m-%d")}</p>
        <div>{safe_content}</div>
    </article>
"""
    
    html_content = f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>#{tag} - My Jakobsson</title>
    <link rel="stylesheet" href="../../css/style.css">
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1>My Jakobsson</h1>
            <p>tankar</p>
        </div>
    </header>
    {nav_html}
    <main class="grid">
        <h1>#{tag}</h1>
        {posts_html}
    </main>
</body>
</html>"""
    
    output_dir = Path('output')
    tag_dir = output_dir / "tags" / tag.replace(" ", "-").lower()
    tag_dir.mkdir(parents=True, exist_ok=True)
    
    index_file = tag_dir / "index.html"
    index_file.write_text(html_content, encoding="utf-8")





def make_tags_index_html(posts):
    """Generates an index page listing all tags."""
    output_dir = Path('output')
    nav_html = create_nav(active_page='tags', depth=1)
    
    all_tags = Counter()
    for post in posts:
        for tag in post.get("tags", []):
            all_tags[tag] += 1
    
    sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
    
    tags_html = ""
    for tag, count in sorted_tags:
        tag_slug = tag.replace(" ", "-").lower()
        tags_html += f'<li><a href="{tag_slug}/index.html">{html.escape(tag)}</a> ({count})</li>\n'
    
    html_content = f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Arkiv - My Jakobsson</title>
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
    <div class="grid">
        <div class="card">
            <h1>Arkiv</h1>
            <h3>Djupdykningar</h3>
            <ul>
                <li><a href="https://tankar.myjak.net/posts/2026-08-17-att-se-in-i-framtiden.html">Att se in i framtiden</a></li>
            </ul>
            <h3>Blogginlägg utifrån kategori</h3>
            <ul>
                {tags_html}
            </ul>
            <p><b>Notera:</b> Taggen "poesi" är inte en komplett samling. Den fyller endast funktionen att informera prenumeranter om nypublicerad poesi. Det fullständiga poesiarkivet <a href="https://poesi.myjak.net">finns här</a>. <b>Eventuella korrigeringar och omarbetningar sker endast i det arkivet</b>.</p>
        </div>
    </div>
</body>
</html>"""
    
    tags_dir = output_dir / "tags"
    tags_dir.mkdir(parents=True, exist_ok=True)
    
    index_file = tags_dir / "index.html"
    index_file.write_text(html_content, encoding="utf-8")



def create_microblog_rss_file(posts):
    """Skapa RSS-fil för mikrobloggen (max 100 senaste inlägg)"""
    from datetime import datetime
    
    # Begränsa till 100 senaste
    limited_posts = posts[:100]
    
    # Konvertera timestamp till RFC 2822 format för RSS
    def iso_to_rfc2822(iso_timestamp):
        # Förväntar: "2026-08-18T15:30:45"
        dt = datetime.fromisoformat(iso_timestamp)
        # RFC 2822: "Sun, 18 Aug 2026 15:30:45 +0000"
        return dt.strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    items_xml = ''
    for post in limited_posts:
        title = post['content'][:50].replace('<', '').replace('>', '') + '...' if len(post['content']) > 50 else post['content'].replace('<', '').replace('>', '')
        pub_date = iso_to_rfc2822(post['timestamp'])
        
        items_xml += f'''    <item>
        <title>{escape_xml(title)}</title>
        <link>https://tankar.myjak.net/micro/</link>
        <pubDate>{pub_date}</pubDate>
        <description><![CDATA[{post['content']}]]></description>
    </item>
'''
    
    rss_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Mikroblogg - My Jakobsson</title>
        <link>https://tankar.myjak.net/micro/</link>
        <description>Korta tankar och snabba anteckningar</description>
        <language>sv</language>
        {items_xml}
    </channel>
</rss>'''
    
    rss_file = Path('output') / 'rss-micro.xml'
    rss_file.write_text(rss_content, encoding='utf-8')




def generate_rss_feeds(posts):
    """Genererar rss.xml (alla inlägg) och rss-ETIKETT.xml för varje etikett"""
    
    # Filtrera bort mikrobloggposter - behåll bara reguljära blogginlägg
    posts = [p for p in posts if not p.get('xml_filename', '').startswith('posts/micro/')]
    
    # Applicera bildbehandling på alla inlägg
    processed_posts = []
    for post in posts:
        post_copy = post.copy()
        post_copy["content"] = process_images_in_content(post_copy.get("content", ""))
        processed_posts.append(post_copy)
    
    all_tags = set()
    for post in processed_posts:
        all_tags.update(post.get("tags", []))
    
    for tag in all_tags:
        filtered_posts = [p for p in processed_posts if tag in p.get("tags", [])]
        create_rss_file(filtered_posts, f"rss-{tag}.xml", tag)
    
    create_rss_file(processed_posts, "rss.xml", None)


# Skapa meny
def create_nav(active_page=None, depth=0):
    """
    Creates navigation menu with relative paths based on depth in directory tree.
    depth=0: root level (index.html)
    depth=1: one level deep (tags/index.html, pages/rss.html)
    depth=2: two levels deep (tags/slug/index.html)
    """
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




def create_rss_file(posts, filename, tag=None):
    """Skapar en RSS-fil för givna inlägg"""
    tag_title = f" - {tag}" if tag else ""
    
    # Börja RSS-XML manuellt
    rss_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        '<channel>',
        f'<title>{escape_xml(SITE_TITLE + tag_title)}</title>',
        f'<link>{SITE_URL}</link>',
        f'<description>{escape_xml(SITE_DESCRIPTION)}</description>',
    ]
    
    for post in posts:
        date_part = post["date"].strftime("%Y-%m-%d")
        post_slug = slugify(post["title"])
        rss_date = post["date"].strftime("%a, %d %b %Y %H:%M:%S +0000")
        
        rss_lines.extend([
            '<item>',
            f'<title>{escape_xml(post["title"])}</title>',
            f'<link>{SITE_URL}/posts/{date_part}-{post_slug}.html</link>',
            '<description>',
            f'<![CDATA[{post["content"]}]]>',
            '</description>',
            f'<pubDate>{rss_date}</pubDate>',
        ])
        
        if post.get("tags"):
            for tag_name in post["tags"]:
                rss_lines.append(f'<category>{escape_xml(tag_name)}</category>')
        
        rss_lines.append('</item>')
    
    rss_lines.extend([
        '</channel>',
        '</rss>',
    ])
    
    output_path = OUTPUT_DIR / filename
    with open(output_path, 'w', encoding='UTF-8') as f:
        f.write('\n'.join(rss_lines))


def escape_xml(text):
    """Escapar XML-specialtecken"""
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&apos;'))





def save_post(title, date, content, tags_str, xml_filename=None):
    if not xml_filename:
        date_part = date.strftime("%Y-%m-%d")
        slug = slugify(title)
        xml_filename = POSTS_DIR / f"{date_part}-{slug}.xml"
    else:
        xml_filename = Path(xml_filename)
  

    # Normalize curly quotes to straight quotes in links
    content = content.replace('="', '="')  
    content = content.replace('">', '">')  

    # Ensure content starts with <p> and ends with </p>
    if not content.startswith('<p>'):
        content = f'<p>{content}'
    if not content.endswith('</p>'):
        content = f'{content}</p>'  
    tags = [tag.strip() for tag in tags_str.split(",") if tag.strip()]

    
    root = ET.Element("post")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "date").text = date.strftime("%Y-%m-%dT%H:%M:%S")
    ET.SubElement(root, "content").text = content
    
    tags_elem = ET.SubElement(root, "tags")
    for tag in tags:
        ET.SubElement(tags_elem, "tag").text = tag
    
    tree = ET.ElementTree(root)
    tree.write(str(xml_filename), encoding="UTF-8", xml_declaration=True)





def rebuild_outputs():
    """Regenerera alla statiska HTML-filer"""
    posts = load_posts()
    
    # Generera paginerad blogg-index
    make_paginated_index_html(posts, posts_per_page=10)
    
    for post in posts:
        if post:
            post_html = make_post_html(post)
            output_file = Path('output/posts') / post['filename']
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(post_html, encoding='utf-8')
    
    # Generera tagg-sidor
    make_tags_index_html(posts)
    for post in posts:
        if post and 'tags' in post:
            for tag in post['tags']:
                make_tag_index_html(post, tag, posts)
    
    # Generera speci-sidor
    make_faq_html()
    make_rss_page_html(posts)
    make_poesi_html()
    make_om_html()
    
    # Generera RSS-feeds
    generate_rss_feeds(posts)
    
    # Generera mikroblogg
    micro_posts = load_microblog_posts()
    make_microblog_html(micro_posts)





print("✓ Exporterat alla inlägg, index, tags och RSS")


# ==================== ADMIN ROUTES (localhost) ====================

@app.route("/")
def index():
    """Hem-sidan med admin-funktioner (localhost)"""
    posts = load_posts()
    generate_rss_feeds(posts)
    return make_index_html(posts, include_admin_nav=True)


@app.route("/posts/<filename>")
def post_page(filename):
    """Blogginläggen med admin-nav (localhost)"""
    for post in load_posts():
        if post["filename"] == filename:
            return make_post_html(post, include_admin_nav=True)
    return "Inlägget hittades inte", 404


@app.route('/micro-create')
def micro_create():
    """Visa formulär för nytt microblogs-inlägg (endast admin)"""
    return render_template('micro_create.html')

@app.route('/micro-post', methods=['POST'])
def micro_post():
    """Spara microblogs-inlägg och exportera (endast admin)"""
    content = request.form.get('content', '').strip()
    
    if not content:
        return render_template('micro_create.html', error='Inlägget kan inte vara tomt!')
    
    save_microblog_post(content)
    
    # Regenerera microblogs-sidorna
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
        <p><a href="/" class="button">← Tillbaka</a></p>
    </body>
    </html>
    '''



@app.route("/create", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        date = request.form.get("date", "").strip()
        content = request.form.get("content", "").strip()
        tags = request.form.get("tags", "").strip()
        
        if title and date and content:
            save_post(title, date, content, tags)
            return redirect("/")
        return "Fel: Alla fält krävs"
    
    default_date = datetime.now().strftime("%Y-%m-%dT%H:%M")
    return render_template("create.html", default_date=default_date)

@app.route("/edit/<filename>", methods=["GET", "POST"])
def edit(filename):
    xml_file = POSTS_DIR / filename  
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        date = request.form.get("date", "").strip()
        content = request.form.get("content", "").strip()
        tags = request.form.get("tags", "").strip()
        
        if title and date and content:
            save_post(title, date, content, tags, str(xml_file))
            return redirect("/")
        return "Fel: Alla fält krävs"
    
    post = get_post_by_xml_filename(filename)  
    if not post:
        return "Inlägget hittades inte", 404
    
    return render_template("edit.html", post=post)


@app.route("/export")
def export_site():
    """Exportera HTML-sidan"""
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



if __name__ == "__main__":
    app.run(debug=True)
