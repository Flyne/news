from flask import Flask, render_template_string
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def fetch_bbc():
    url = 'https://www.bbc.com/news'
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    headlines = soup.select('h3')[:5]
    return [('BBC', h.get_text(strip=True), 'https://www.bbc.com' + 
h.find_parent('a')['href']) 
            for h in headlines if h.find_parent('a') and 
h.find_parent('a').has_attr('href')]

def fetch_cnn():
    url = 'https://edition.cnn.com'
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    links = soup.select('a[href^="/2025"]')[:5]
    return [('CNN', link.get_text(strip=True), url + link['href']) 
            for link in links if link.get_text(strip=True)]

def fetch_reuters():
    url = 'https://www.reuters.com'
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    headlines = soup.select('a[href^="/world"], a[href^="/business"]')[:5]
    return [('Reuters', h.get_text(strip=True), url + h['href']) 
            for h in headlines if h.get_text(strip=True)]

@app.route('/')
def index():
    headlines = fetch_bbc() + fetch_cnn() + fetch_reuters()
    html = '''
    <html>
    <head>
        <title>🗞 Top News Headlines</title>
        <style>
            body { font-family: sans-serif; margin: 2rem; }
            .headline { margin-bottom: 1rem; }
            h1 { color: #333; }
        </style>
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
