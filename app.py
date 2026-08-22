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

HYVOR_ID = os.environ.get('HYVOR_ID', '15846')

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
        
        <p>RSS är ett sätt att prenumerera på uppdateringar från mig. Du behöver en RSS-läsare (såsom Feedly, Microsoft Outlook, eller Thunderbird) för att läsa flödena. Att prenumerera är gratis, och jag kan inte spåra vem som prenumerar. RSS-läsare har vanligtvis en fördröjning på alltifrån 20 minuter till en dag på hur ofta de tittar efter uppdateringar, så du kommer inte att bli meddelad i samma sekund som jag postar något. </p>

<p>Du kan välja på att prenumerera på alla mina inlägg i en enda jätte-RSS (mikrobloggen exkluderad), eller att prenumerera på enskilda kategorier:</p>

        <h3>Huvudflöde</h3>
        <ul>
            <li><a href="/rss.xml">Alla inlägg</a> (utom mikrobloggen)</li>
        </ul>

        <h3>Mikrobloggen</h3>
        <ul>
        <a href="/rss-micro.xml">Mikroblogg</a>        </ul>

        <h3>Flöden per kategori</h3>
        <ul>
        {tag_feeds}        </ul>



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
    
    return html  # ← LÄGG TILL DENNA RAD


def escape_xml(text):
    """Escapar XML-specialtecken"""
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&apos;'))

def create_rss_file(posts, filename, tag=None):
    """Skapar en RSS-fil för de givna inläggen"""
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
    <channel>
        <title>{escape_xml(SITE_TITLE)}{f' - {tag}' if tag else ''}</title>
        <link>{SITE_URL}</link>
        <description>{escape_xml(SITE_DESCRIPTION)}</description>
        <language>sv</language>
"""
    
    for post in posts:
        content_processed = process_images_in_content(post.get("content", ""))
        date_obj = datetime.strptime(post["date"], "%Y-%m-%dT%H:%M")
        rss_date = date_obj.strftime("%a, %d %b %Y %H:%M:%S +0000")
        post_url = f"{SITE_URL}/posts/{post['filename']}"
        
        rss += f"""        <item>
            <title>{escape_xml(post['title'])}</title>
            <link>{post_url}</link>
            <pubDate>{rss_date}</pubDate>
            <description>{escape_xml(post['content'][:300])}</description>
            <content:encoded><![CDATA[{content_processed}]]></content:encoded>
        </item>
"""
    
    rss += """    </channel>
</rss>"""
    
    output_file = Path('output') / filename
    output_file.write_text(rss, encoding='utf-8')

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


def get_months_from_posts(posts):
    """Organisera inlägg efter år och månad (nyast först)"""
    month_names_sv = {
        1: "Januari", 2: "Februari", 3: "Mars", 4: "April",
        5: "Maj", 6: "Juni", 7: "Juli", 8: "Augusti",
        9: "September", 10: "Oktober", 11: "November", 12: "December"
    }
    
    months_dict = {}
    for post in posts:
        try:
            date_part = post["date"].split("T")[0]  # YYYY-MM-DD
            year, month, day = date_part.split("-")
            year = int(year)
            month = int(month)
            
            key = f"{year}-{month:02d}"  # "2024-01"
            
            if key not in months_dict:
                months_dict[key] = {
                    "year": year,
                    "month": month,
                    "month_name": month_names_sv.get(month, ""),
                    "posts": []
                }
            
            months_dict[key]["posts"].append(post)
        except:
            continue
    
    # Sortera nyast först
    sorted_months = sorted(months_dict.items(), key=lambda x: x[0], reverse=True)
    return dict(sorted_months)


def save_post(title, date, content, tags_str, xml_filename=None):
    if not xml_filename:
        date_part = date.split("T")[0]
        slug = slugify(title)
        xml_filename = POSTS_DIR / f"{date_part}-{slug}.xml"
    else:
        xml_filename = Path(xml_filename)
    
    content = content.replace('="', '="')
    content = content.replace('">', '">')
    
    # Kontrollera om innehållet redan är omslaget av block-element
    has_block_element = (any(content.strip().startswith(f'<{tag}') 
                            for tag in ['div', 'p', 'article', 'section', 'blockquote']) or
                        any(content.strip().endswith(f'</{tag}>') 
                            for tag in ['div', 'p', 'article', 'section', 'blockquote']))
    
    if not has_block_element:
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



# SKAPA MENYN
def create_nav(active_page=None, depth=0):
    """Creates navigation menu with relative paths based on depth."""
    prefix = "../" * depth
    
    nav_items = [
        (f"{prefix}index.html", "Hem", "home"),
        (f"{prefix}pages/poesi.html", "Poesi", "poesi"),
        (f"{prefix}micro/index.html", "Mikroblogg", "micro"),
        (f"{prefix}pages/faq.html", "FAQ", "faq"),
        (f"{prefix}pages/rss.html", "RSS", "rss"),
        (f"{prefix}tags/index.html", "Arkiv", "tags"),
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

        if include_admin_nav:
            link = f"/posts/{post['filename']}"
            xml_filename = post.get("xml_filename", "")
            edit_button = f'<a href="/edit/{xml_filename}" style="color:#ff9800; margin-left:10px;">✎ Redigera</a>'
        else:
            link = f"posts/{post['filename']}"
            edit_button = ""
        
        # Kommentera-länk
        comment_link = f'<a href="{link}#kommentarer" style="text-decoration: none; color: #666;">Kommentera →</a>'
        
        cards += f"""
        <div class="card">
            <h2><a href="{link}">{safe_title}</a>{edit_button}</h2>
            <div class="date-tags-wrapper">
                <span class="date">{safe_date}</span>
            </div>
            <div>{safe_content}</div>            
            <div class="comment-tags-wrapper">
                <div class="comment-link">{comment_link}</div>
                <div class="tags">{tags_html}</div>
            </div>

            
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
        nav_section = f"""    <nav class="menu">
{nav_html}
    </nav>"""

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
        nav_html = f""" <a href="/">Hem</a>
<a href="/create">Skapa inlägg</a>
<a href="/export">Exportera</a>
<a href="/edit/{xml_filename}" style="color:#ff9800;">✎ Redigera</a>"""
    else:
        nav_html = create_nav(active_page='posts', depth=1)
    
    # Unik identifierare för varje inlägg (använd filnamnet som ID)
    post_id = post['filename'].replace('.html', '').replace('-', '_')
    
    # Generera tagg-HTML
    tags_html = ""
    if post.get("tags"):
        tag_links = []
        for tag in post["tags"]:
            tag_slug = tag.replace(" ", "-").lower()
            tag_links.append(f'<a href="../tags/{tag_slug}/" style="text-decoration: none;"><span class="tag">{html.escape(tag)}</span></a>')
        tags_html = " ".join(tag_links)
    
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
<div class="date-tags-wrapper">
    <span class="date">{safe_date}</span>
</div>
<div>{safe_content}</div>

<div class="comment-tags-wrapper">
    <div class="tags">{tags_html}</div>
</div>

<p><a href="../index.html">← Tillbaka till startsidan</a></p>

<!-- Hyvor Comments -->
<div id="kommentarer"><hyvor-talk-comments
	website-id="{HYVOR_ID}"
	page-id="{post_id}"
></hyvor-talk-comments>
<script async src="https://talk.hyvor.com/embed/embed.js" type="module"></script></div>

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
<p>Endast ny poesi läggs ut här i bloggen, i syfte att det ska gå att prenumerera på den <a href="https://tankar.myjak.net/rss-poesi.xml">via RSS</a> (<a href="rss.html">info</a>). <b>Eventuella korrigeringar och omarbetningar av mina dikter publiceras enbart på sidan ovan,</b> så om du vill citera mig, använd helst den sidan som källa för att säkerställa att du har den senaste versionen av dikten.</p><p>Tack!</p>
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


def extract_excerpt(post_content, words=50):
    """Extraherar första N ord från post-innehål med proper HTML-hantering"""
    from html.parser import HTMLParser
    import html
    
    class ExcerptParser(HTMLParser):
        def __init__(self, max_words):
            super().__init__()
            self.max_words = max_words
            self.word_count = 0
            self.output = []
            self.open_tags = []  # Spåra vilka taggar som är öppna
            
        def handle_starttag(self, tag, attrs):
            if self.word_count < self.max_words:
                # Lägg till öppnande tagg
                attr_str = ' '.join([f'{k}="{v}"' for k, v in attrs])
                if attr_str:
                    self.output.append(f'<{tag} {attr_str}>')
                else:
                    self.output.append(f'<{tag}>')
                self.open_tags.append(tag)
                
        def handle_endtag(self, tag):
            if self.word_count < self.max_words:
                self.output.append(f'</{tag}>')
                if tag in self.open_tags:
                    self.open_tags.remove(tag)
                
        def handle_data(self, data):
            if self.word_count >= self.max_words:
                return
                
            words_list = data.split()
            remaining = self.max_words - self.word_count
            
            if remaining > 0:
                self.output.append(' '.join(words_list[:remaining]))
                self.word_count += len(words_list[:remaining])
    
    parser = ExcerptParser(words)
    parser.feed(html.unescape(post_content))
    
    # Stäng alla kvarvarande öppna taggar
    while parser.open_tags:
        tag = parser.open_tags.pop()
        parser.output.append(f'</{tag}>')
    
    excerpt = ''.join(parser.output).strip() + '...'
    return excerpt





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
                    tags_html = f'<div class="tags" style="text-align: right; margin-top: 0rem;">{tags_html}</div>'
                
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

    # Generera arkiv-sida
    all_tags = set()
    for post in posts:
        all_tags.update(post.get("tags", []))
    all_tags.discard("poesi") # lista inte poesi i arkivet
    tags = sorted(list(all_tags))
    
    posts_without_poesi = [p for p in posts if "poesi" not in p.get("tags", [])]
    months = get_months_from_posts(posts_without_poesi) # ta inte med poesi i arkivet
    
    archive_html = render_template("archive.html",
                                   tags=tags,
                                   months=months,
                                   site_title=SITE_TITLE,
                                   site_description=SITE_DESCRIPTION,
                                   nav_html=create_nav(active_page='tags', depth=1))
    
    archive_dir = Path('output/tags')
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / 'index.html').write_text(archive_html, encoding='utf-8')
    print("✓ Arkiv regenererat")

    # Generera tag-specifika arkiv-sidor
    print("Börjar generera tag-sidor...")
    for tag in tags:
        if tag == "poesi":  # Hoppa över poesi-taggen
            continue
        
        tag_slug = slugify(tag)
        filtered_posts = [p for p in posts if tag in p.get("tags", []) and "poesi" not in p.get("tags", [])]
        
        # Lägg till excerpts till varje inlägg (använd post['content'] direkt)
        for post in filtered_posts:
            try:
                post['excerpt'] = extract_excerpt(html.unescape(post.get('content', '')), words=50)
            except Exception as e:
                print(f"  Varning: Kunde inte skapa excerpt för {post['filename']}: {e}")
                post['excerpt'] = ""
        
        months = get_months_from_posts(filtered_posts)
        
        print(f"  Tag: {tag}, Slug: {tag_slug}, Inlägg: {len(filtered_posts)}")
        
        if filtered_posts:
            print(f"  Första post skrivs ")
        
        try:
            tag_html = render_template("tag_archive.html", 
                           posts=filtered_posts, 
                           tag=tag, 
                           months=months,
                           nav_html=create_nav(active_page='tags', depth=2),
                           site_title=SITE_TITLE,
                           site_description=SITE_DESCRIPTION)
            print(f"  render_template lyckades för {tag}")
        except Exception as e:
            print(f"  ERROR i render_template: {str(e)}")
            continue
        
        try:
            tag_dir = Path('output/tags') / tag_slug
            tag_dir.mkdir(parents=True, exist_ok=True)
            (tag_dir / 'index.html').write_text(tag_html, encoding='utf-8')
            print(f"  ✓ Tag-sida '{tag}' sparad")
        except Exception as e:
            print(f"  ERROR vid sparande: {str(e)}")

    print("✓ Tag-sidor klara")

    # Generera FAQ-sida
    make_faq_html() 

    # Generera poesisida
    make_poesi_html() 

    # Generera om (kontaktsida)
    make_om_html() 

    # Generera RSS-flöden
    generate_rss_feeds(posts)
    
    # Generera RSS-sida
    rss_page_html = make_rss_page_html(posts)
    rss_output_dir = Path('output/pages')
    rss_output_dir.mkdir(parents=True, exist_ok=True)
    (rss_output_dir / 'rss.html').write_text(rss_page_html, encoding='utf-8')





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
                tags_html = f'<div class="tags" style="text-align: right; margin-top: 0rem;">{tags_html}</div>'
            
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

@app.route("/tags")
def archive():
    """Arkivsida med tabs för tags och månader"""
    try:
        posts = load_posts()
        tags = sorted(set(tag for post in posts for tag in post.get("tags", [])))
        months = get_months_from_posts(posts)
        nav_html = create_nav(active_page='tags', depth=1)
        
        return render_template(
            "archive.html",
            tags=tags,
            months=months,
            nav_html=nav_html,
            site_title=SITE_TITLE,
            site_description=SITE_DESCRIPTION
        )
    except Exception as e:
        print(f"Error in archive route: {e}")
        return f"Error: {str(e)}", 500

@app.route("/tags/<tag_slug>")
def show_tag(tag_slug):
    """Visa alla inlägg för en specifik tag"""
    try:
        posts = load_posts()
        
        # Konvertera slug tillbaka till original tag-namn
        # (t.ex. "mitt-tag" → "mitt tag")
        tag_name = tag_slug.replace('-', ' ').title()
        
        # Filtrera inlägg som har denna tag
        filtered_posts = [p for p in posts if tag_name in p.get("tags", [])]
        
        if not filtered_posts:
            return "Ingen inlägg med denna tag", 404
        
        nav_html = create_nav(active_page='tags', depth=2)
        
        return render_template(
            "tag_archive.html",
            tag=tag_name,
            posts=filtered_posts,
            nav_html=nav_html,
            site_title=SITE_TITLE,
            site_description=SITE_DESCRIPTION
        )
    except Exception as e:
        print(f"Error in show_tag route: {e}")
        return f"Error: {str(e)}", 500


if __name__ == "__main__":
    app.run(debug=True)
