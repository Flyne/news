from flask import Flask, render_template_string
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def fetch_bbc():
    url = 'https://www.bbc.com/news'
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    headlines = []
    for item in soup.select('h3.gs-c-promo-heading__title'):
        title = item.get_text(strip=True)
        link = item.find_parent('a')['href']
        if not link.startswith('http'):
            link = 'https://www.bbc.com' + link
        headlines.append(('BBC', title, link))
        if len(headlines) >= 5:
            break
    return headlines

def fetch_cnn():
    url = 'https://edition.cnn.com/world'
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    headlines = []
    for item in soup.select('h3.cd__headline a'):
        title = item.get_text(strip=True)
        link = item['href']
        if not link.startswith('http'):
            link = 'https://edition.cnn.com' + link
        headlines.append(('CNN', title, link))
        if len(headlines) >= 5:
            break
    return headlines

def fetch_reuters():
    url = 'https://www.reuters.com/world/'
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    headlines = []
    for item in soup.select('article.story h3.story-title, article div.story-content a'):
        title = item.get_text(strip=True)
        link = item.find_parent('a')['href'] if item.find_parent('a') else item['href']
        if not link.startswith('http'):
            link = 'https://www.reuters.com' + link
        headlines.append(('Reuters', title, link))
        if len(headlines) >= 5:
            break
    return headlines

@app.route('/')
def index():
    headlines = fetch_bbc() + fetch_cnn() + fetch_reuters()
    html = '''
    <html>
    <head>
        <title>🗞 Top News Headlines</title>
        <style>
            body { font-family: sans-serif; margin: 2rem; background: #f4f4f4; color: #222; }
            .headline { margin-bottom: 1rem; padding: 10px; background: white; border-radius: 6px; box-shadow: 0 0 5px #ccc; }
            a { text-decoration: none; color: #0077cc; }
            a:hover { text-decoration: underline; }
            h1 { color: #333; }
        </style>
        <meta http-equiv="refresh" content="3600" />
    </head>
    <body>
        <h1>📰 Today's Top News</h1>
        {% for source, title, link in headlines %}
            <div class="headline">
                <strong>{{ source }}</strong>: 
                <a href="{{ link }}" target="_blank">{{ title }}</a>
            </div>
        {% endfor %}
    </body>
    </html>
    '''
    return render_template_string(html, headlines=headlines)

if __name__ == '__main__':
    app.run(debug=True)
