<!doctype html>
<html lang="sv">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="../../css/style.css">
    <title>{{ tag }} - {{ site_title }}</title>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1>{{ site_title }}</h1>
            <p>{{ site_description }}</p>
        </div>
    </header>
    
    {{ nav_html | safe }}
    
    <div class="grid">
        <div class="card">
            <h2>Inlägg med taggen "{{ tag }}"</h2>
            <p>{{ posts | length }} inlägg</p>
            
            <div class="posts-list">
                {% for post in posts %}
                    <div class="post-item">
                        <h3><a href="/posts/{{ post.filename }}">{{ post.title }}</a></h3>
                        <p class="post-meta">{{ post.date[:10] }}</p>
                    </div>
                {% endfor %}
            </div>
        </div>
    </div>
</body>
</html>
