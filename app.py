from flask import Flask, render_template_string, request, jsonify, send_file
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import json
import io # To handle audio data in memory

app = Flask(__name__)

# User-Agent to mimic a common browser, helps avoid some basic blocking
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36 Edg/109.0.1518.78',
    'Referer': 'https://www.google.com/', 
    'Accept-Language': 'en-US,en;q=0.9'
}

# --- Centralized News Source Configuration ---
NEWS_CONFIG = {
    'general': {
        'BBC News': {
            'url': 'https://www.bbc.com/news',
            'selector': 'h3.gs-c-promo-heading__title, a.gs-c-promo-heading',
            'base_url': 'https://www.bbc.com',
            'snippet': 'Click to read more on BBC News.',
            'icon': '📰'
        },
        'CNN': {
            'url': 'https://edition.cnn.com/world',
            'selector': 'h3.cd__headline a, .container__headline-text',
            'base_url': 'https://edition.cnn.com',
            'snippet': 'Read full story on CNN.',
            'icon': '🌍'
        },
        'Reuters': {
            'url': 'https://www.reuters.com/world/',
            'selector': 'a.media-story-card__body__link, a.story-link, div.story-content h3 a',
            'base_url': 'https://www.reuters.com',
            'snippet': 'Read more on Reuters.',
            'icon': '✍️'
        },
        'The Guardian': {
            'url': 'https://www.theguardian.com/international',
            'selector': 'h3[data-linker-name="article"] a',
            'base_url': 'https://www.theguardian.com',
            'snippet': 'Discover more on The Guardian.',
            'icon': '🇬🇧'
        }
    },
    'startup': {
        'TechCrunch': {
            'url': 'https://techcrunch.com/',
            'selector': 'h2.wp-block-post-title a, h3.wp-block-post-title a',
            'base_url': 'https://techcrunch.com',
            'snippet': 'Catch the latest startup news on TechCrunch.',
            'icon': '💡'
        },
        'Sifted': {
            'url': 'https://sifted.eu/',
            'selector': 'h3.article-title__heading a',
            'base_url': 'https://sifted.eu',
            'snippet': 'Get European startup insights from Sifted.',
            'icon': '🇪🇺'
        },
        'VentureBeat': {
            'url': 'https://venturebeat.com/',
            'selector': 'h2.ArticleListing__title a, h3.ArticleListing__title a, h4.ArticleListing__title a',
            'base_url': 'https://venturebeat.com',
            'snippet': 'Stay updated with VentureBeat.',
            'icon': '🚀'
        },
        'Inc.': {
            'url': 'https://www.inc.com/startup',
            'selector': 'div.text-body a, h2.headline a, h3.headline a',
            'base_url': 'https://www.inc.com',
            'snippet': 'Read more on Inc.com for entrepreneurs.',
            'icon': '📈'
        },
        'Crunchbase News': {
            'url': 'https://news.crunchbase.com/',
            'selector': 'h2.cb-news-card-title a, h3.cb-news-card-title a',
            'base_url': 'https://news.crunchbase.com',
            'snippet': 'Explore funding news on Crunchbase News.',
            'icon': '💰'
        }
    }
}

# --- Helper function for robust fetching of headlines ---
def fetch_headlines_from_url(source_info, news_type, source_name):
    headlines = []
    url = source_info['url']
    headline_selector = source_info['selector']
    base_url = source_info['base_url']
    snippet_text = source_info['snippet']
    icon = source_info['icon']

    try:
        r = requests.get(url, timeout=10, headers=HEADERS)
        r.raise_for_status() 
        soup = BeautifulSoup(r.text, 'html.parser')
        
        items_to_process = soup.select(headline_selector)[:20] 

        for i, item in enumerate(items_to_process):
            title = item.get_text(strip=True)
            link = '#' 
            
            link_element = None
            if item.name == 'a' and 'href' in item.attrs:
                link_element = item
            else: 
                link_element = item.find('a')
                if not link_element: 
                    link_element = item.find_parent('a')
            
            if link_element and 'href' in link_element.attrs:
                link = link_element['href']

            if link and not link.startswith('http'):
                if link.startswith('//'): 
                    link = 'https:' + link
                else:
                    link = base_url + link
            
            if not title or link == '#' or 'javascript:void(0)' in link or link.endswith(('.mp4', '.mov', '.pdf')):
                continue 

            article_id = f"{news_type}_{source_name}_{abs(hash(link))}" if link != '#' else f"no_link_{news_type}_{source_name}_{i}"

            headlines.append({
                'id': article_id, 
                'title': title,
                'link': link,
                'snippet': snippet_text,
                'publish_time': '', # Publication time is hard to reliably scrape for all
                'source_name': source_name, # Add source name to headline data
                'news_type': news_type, # Add news type (general/startup) to headline data
                'icon': icon # Add icon to headline data
            })
            
    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error for {url} ({source_name}): {errh}")
        headlines.append({'id': f"error_{source_name}", 'title': f"Could not fetch news from {source_name}", 'link': '#', 'snippet': f"Error: {errh}", 'is_error': True, 'source_name': source_name, 'news_type': news_type, 'icon': icon})
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting to {url} ({source_name}): {errc}")
        headlines.append({'id': f"error_{source_name}", 'title': f"Could not connect to {source_name}", 'link': '#', 'snippet': f"Error: {errc}", 'is_error': True, 'source_name': source_name, 'news_type': news_type, 'icon': icon})
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error for {url} ({source_name}): {errt}")
        headlines.append({'id': f"error_{source_name}", 'title': f"Timed out fetching {source_name}", 'link': '#', 'snippet': f"Error: {errt}", 'is_error': True, 'source_name': source_name, 'news_type': news_type, 'icon': icon})
    except requests.exceptions.RequestException as err:
        print(f"Something went wrong with request to {url} ({source_name}): {err}")
        headlines.append({'id': f"error_{source_name}", 'title': f"Request error for {source_name}", 'link': '#', 'snippet': f"Error: {err}", 'is_error': True, 'source_name': source_name, 'news_type': news_type, 'icon': icon})
    except Exception as e:
        print(f"An unexpected error occurred while fetching {url} ({source_name}): {e}")
        headlines.append({'id': f"error_{source_name}", 'title': f"An unknown error occurred for {source_name}", 'link': '#', 'snippet': f"Error: {e}", 'is_error': True, 'source_name': source_name, 'news_type': news_type, 'icon': icon})
    return headlines

# --- Function to fetch all news from all configured sources ---
def fetch_all_news():
    all_headlines = []
    for news_type, sources in NEWS_CONFIG.items():
        for source_name, source_info in sources.items():
            all_headlines.extend(fetch_headlines_from_url(source_info, news_type, source_name))
    return all_headlines

# --- Main App Route ---
@app.route('/')
def index():
    all_news_items = fetch_all_news()

    # Group news items by their source name for easier rendering in template
    grouped_news_by_source = {}
    for headline in all_news_items:
        source = headline.get('source_name')
        if source not in grouped_news_by_source:
            grouped_news_by_source[source] = []
        grouped_news_by_source[source].append(headline)
    
    # Sort source names (e.g., general first, then startup, and within each, alphabetically)
    sorted_source_groups = []
    for news_type_key in ['general', 'startup']:
        for source_name in sorted(NEWS_CONFIG.get(news_type_key, {}).keys()):
            if source_name in grouped_news_by_source:
                sorted_source_groups.append((source_name, grouped_news_by_source[source_name]))

    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🗞 Your Daily News </title>
        <!-- Meta tags for SEO -->
        <meta name="description" content="Your daily news aggregator with personalized podcast summaries. Select articles and get an AI-generated audio briefing.">
        <meta name="keywords" content="news, daily briefing, startup news, general news, podcast, AI summary, personalized news">

        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary-color: #FF69B4; /* Neon Pink */
                --primary-hover-color: #FA8072; /* Slightly darker pink on hover */
                --background-color: #f0f2f5;
                --card-background: #ffffff;
                --text-color: #333;
                --heading-color: #1a1a1a;
                --snippet-color: #555;
                --time-color: #888;
                --border-color: #e0e0e0;
                --selected-border: var(--primary-color);
                --selected-background: #ffe3f1; /* Light pink for selected cards */
                --error-color: #dc3545;

                /* Dark Mode variables */
                --dark-bg: #282c34;
                --dark-card-bg: #3c414d;
                --dark-text: #e0e0e0;
                --dark-heading: #ffffff;
                --dark-snippet: #bbbbbb;
                --dark-time: #aaaaaa;
                --dark-border: #4a505c;
                --dark-podcast-controls-bg: #343a40;
            }

            body { 
                font-family: 'Montserrat', sans-serif; 
                background: var(--background-color); 
                color: var(--text-color); 
                margin: 0; 
                padding: 1.5rem; /* Reduced padding */
                line-height: 1.6;
                transition: background-color 0.3s, color 0.3s;
            }
            body.dark-mode {
                background: var(--dark-bg);
                color: var(--dark-text);
            }
            body.dark-mode h1,
            body.dark-mode .source-title {
                color: var(--dark-heading);
            }
            body.dark-mode .intro-message,
            body.dark-mode .snippet,
            body.dark-mode .time,
            body.dark-mode .tab-button {
                color: var(--dark-snippet);
            }
            body.dark-mode .card {
                background: var(--dark-card-bg);
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            }
            body.dark-mode .card a {
                color: var(--dark-heading);
            }
            body.dark-mode .podcast-controls {
                background: var(--dark-podcast-controls-bg);
                color: var(--dark-text);
            }
            body.dark-mode .podcast-controls label {
                color: var(--dark-snippet);
            }
            body.dark-mode .podcast-controls #time-display {
                color: #87ceeb; /* Light blue for contrast in dark mode */
            }
            body.dark-mode footer {
                border-top-color: var(--dark-border);
            }
            body.dark-mode #scrollToTopBtn {
                background-color: var(--primary-color); /* Retain neon pink */
            }

            h1 { 
                text-align: center; 
                color: var(--heading-color); 
                margin-bottom: 1rem; /* Reduced margin */
                font-weight: 700;
                font-size: 2.2rem; /* Slightly smaller */
            }
            .top-controls {
                display: flex;
                justify-content: space-between;
                align-items: center;
                max-width: 1200px;
                margin: 0 auto 1.5rem; /* Reduced margin */
                padding: 0 1rem;
            }
            .intro-message { 
                text-align: center;
                max-width: 800px;
                margin: 0 auto 1.5rem; /* Reduced margin */
                font-size: 1rem; /* Slightly smaller font */
                color: var(--snippet-color);
            }

            /* Toggle button styles */
            .toggle-container {
                display: flex;
                align-items: center;
                gap: 8px; /* Space between label and toggle */
            }
            .switch {
                position: relative;
                display: inline-block;
                width: 40px; /* Smaller width */
                height: 22px; /* Smaller height */
            }
            .switch input {
                opacity: 0;
                width: 0;
                height: 0;
            }
            .slider {
                position: absolute;
                cursor: pointer;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: #ccc;
                -webkit-transition: .4s;
                transition: .4s;
                border-radius: 34px;
            }
            .slider:before {
                position: absolute;
                content: "";
                height: 14px; /* Smaller circle */
                width: 14px; /* Smaller circle */
                left: 4px;
                bottom: 4px;
                background-color: white;
                -webkit-transition: .4s;
                transition: .4s;
                border-radius: 50%;
            }
            input:checked + .slider {
                background-color: var(--primary-color);
            }
            input:focus + .slider {
                box-shadow: 0 0 1px var(--primary-color);
            }
            input:checked + .slider:before {
                -webkit-transform: translateX(18px); /* Adjust based on new width */
                -ms-transform: translateX(18px);
                transform: translateX(18px);
            }
            /* Rounded sliders */
            .slider.round {
                border-radius: 34px;
            }
            .slider.round:before {
                border-radius: 50%;
            }


            .podcast-controls {
                text-align: center;
                margin-bottom: 2rem; /* Reduced margin */
                padding: 1rem; /* Reduced padding */
                background: #e9ecef;
                border-radius: 10px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                max-width: 600px;
                margin-left: auto;
                margin-right: auto;
            }
            body.dark-mode .podcast-controls {
                background: var(--dark-podcast-controls-bg);
            }
            .podcast-controls label {
                font-size: 1rem; /* Slightly smaller */
                color: #495057;
                display: block;
                margin-bottom: 0.5rem; /* Reduced margin */
            }
            .podcast-controls input[type="range"] {
                width: 80%;
                margin: 0.3rem auto 0.8rem; /* Reduced margins */
                -webkit-appearance: none; 
                appearance: none;
                height: 6px; /* Thinner slider */
                background: #ddd;
                outline: none;
                border-radius: 5px;
                opacity: 0.7;
                transition: opacity .2s;
            }
            .podcast-controls input[type="range"]:hover {
                opacity: 1;
            }
            .podcast-controls input[type="range"]::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 18px; /* Smaller thumb */
                height: 18px; /* Smaller thumb */
                border-radius: 50%;
                background: var(--primary-color); 
                cursor: pointer;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            .podcast-controls input[type="range"]::-moz-range-thumb {
                width: 18px; /* Smaller thumb */
                height: 18px; /* Smaller thumb */
                border-radius: 50%;
                background: var(--primary-color); 
                cursor: pointer;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            .podcast-controls button {
                padding: 10px 20px; /* Reduced padding */
                background-color: var(--primary-color); 
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 1rem; /* Slightly smaller */
                font-weight: 600;
                cursor: pointer;
                transition: background-color 0.2s ease, transform 0.1s ease;
                box-shadow: 0 3px 6px rgba(0,0,0,0.15);
                margin-top: 0.8rem; /* Reduced margin */
            }
            .podcast-controls button:hover {
                background-color: var(--primary-hover-color); 
                transform: translateY(-1px);
            }
            .podcast-controls #time-display {
                font-size: 1.1rem; /* Slightly smaller */
                font-weight: 600;
                color: #007bff; 
                margin-bottom: 0.5rem; /* Reduced margin */
            }
            .podcast-controls p { /* Tip message */
                font-size: 0.8em; /* Smaller font */
                color: #666; 
                margin-top: 0.3rem; /* Reduced margin */
            }
            body.dark-mode .podcast-controls p {
                color: var(--dark-snippet);
            }


            .news-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); 
                grid-gap: 20px; 
                align-items: start; 
                max-width: 1200px; 
                margin: 0 auto; 
            }
            .source-section { 
                grid-column: 1 / -1; 
                margin-top: 1.5rem; /* Reduced margin */
                margin-bottom: 0.8rem; /* Reduced margin */
                text-align: center;
            }
            .source-title { 
                font-size: 1.8rem; /* Slightly smaller */
                color: var(--heading-color); 
                position: relative;
                padding-bottom: 8px; /* Reduced padding */
                display: inline-block; 
            }
            .source-title::after {
                content: '';
                position: absolute;
                left: 50%;
                bottom: 0;
                transform: translateX(-50%);
                width: 70px; /* Slightly smaller */
                height: 3px; /* Thinner line */
                background-color: #e60023; 
                border-radius: 2px;
            }

            .card { 
                background: var(--card-background); 
                padding: 1.2rem; /* Reduced padding */
                border-radius: 12px; 
                box-shadow: 0 4px 15px rgba(0,0,0,0.08); 
                transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out, background-color 0.2s ease; 
                display: flex;
                flex-direction: column;
                justify-content: space-between; 
                min-height: 150px; 
                border: 1px solid transparent; 
            }
            .card:hover { 
                transform: translateY(-5px); 
                box-shadow: 0 8px 25px rgba(0,0,0,0.12); 
            }
            .card.selected-card { 
                border-color: var(--selected-border);
                background-color: var(--selected-background);
                box-shadow: 0 4px 20px rgba(255, 105, 180, 0.3); 
            }
            body.dark-mode .card.selected-card {
                background-color: #553b47; /* Darker selected background for dark mode */
                border-color: var(--primary-color);
            }

            .card h3 {
                font-size: 1.05rem; /* Slightly smaller */
                margin-top: 0;
                margin-bottom: 0.6rem; /* Reduced margin */
                line-height: 1.3;
            }
            .card h3 a { 
                color: var(--heading-color); 
                text-decoration: none; 
                font-weight: 700;
                display: block; 
            }
            .card h3 a:hover { 
                color: #e60023; 
                text-decoration: underline; 
            }
            .snippet { 
                margin-top: 0.4rem; /* Reduced margin */
                color: var(--snippet-color); 
                font-size: 0.85rem; /* Slightly smaller */
                flex-grow: 1; 
            }
            .card-footer {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 0.8rem; /* Reduced margin */
            }
            .time { 
                font-size: 0.7rem; /* Slightly smaller */
                color: var(--time-color); 
                text-align: right;
            }
            .like-button { 
                background: none;
                border: none;
                font-size: 1.4rem; /* Slightly smaller */
                cursor: pointer;
                color: var(--time-color); 
                transition: color 0.2s ease, transform 0.2s ease;
                padding: 0;
                margin: 0;
            }
            .like-button.selected {
                color: var(--primary-color); 
                transform: scale(1.1);
            }
            .like-button:hover {
                transform: scale(1.2);
            }

            .no-headlines {
                grid-column: 1 / -1; 
                text-align: center;
                color: #666;
                padding: 1rem;
                background: #fff3cd; 
                border: 1px solid #ffeeba;
                border-radius: 8px;
                margin-bottom: 2rem;
            }
            body.dark-mode .no-headlines {
                background: #4d442a;
                border-color: #6e5e33;
                color: #e0e0e0;
            }
            footer {
                text-align: center;
                margin-top: 3rem; /* Reduced margin */
                color: #777;
                font-size: 0.8rem; /* Slightly smaller */
                padding-top: 1rem; /* Reduced padding */
                border-top: 1px solid var(--border-color);
                max-width: 1200px;
                margin-left: auto;
                margin-right: auto;
            }

            /* Scroll to top button */
            #scrollToTopBtn {
                display: none; 
                position: fixed; 
                bottom: 20px; /* Reduced bottom distance */
                right: 20px; /* Reduced right distance */
                z-index: 99; 
                border: none; 
                outline: none; 
                background-color: var(--primary-color); 
                color: white; 
                cursor: pointer; 
                padding: 12px; /* Reduced padding */
                border-radius: 8px; /* Slightly smaller radius */
                font-size: 16px; /* Slightly smaller font */
                box-shadow: 0 4px 8px rgba(0,0,0,0.1); /* Reduced shadow */
                transition: background-color 0.3s, transform 0.2s;
            }
            #scrollToTopBtn:hover {
                background-color: var(--primary-hover-color);
                transform: translateY(-2px);
            }

            /* Dark mode toggle specific styles */
            #darkModeToggleLabel {
                color: var(--text-color);
                font-size: 0.95rem;
            }
            body.dark-mode #darkModeToggleLabel {
                color: var(--dark-text);
            }


            @media (max-width: 768px) {
                body { padding: 1rem; }
                h1 { font-size: 2rem; margin-bottom: 1rem; }
                .intro-message { margin-bottom: 1rem; font-size: 0.95rem; }
                .podcast-controls { margin-bottom: 1rem; padding: 0.8rem; }
                .podcast-controls label { font-size: 0.95rem; margin-bottom: 0.3rem; }
                .podcast-controls input[type="range"] { height: 5px; }
                .podcast-controls input[type="range"]::-webkit-slider-thumb { width: 16px; height: 16px; }
                .podcast-controls input[type="range"]::-moz-range-thumb { width: 16px; height: 16px; }
                .podcast-controls button { padding: 8px 15px; font-size: 0.95rem; margin-top: 0.5rem; }
                .podcast-controls #time-display { font-size: 1rem; margin-bottom: 0.3rem; }
                .podcast-controls p { font-size: 0.75em; }
                .source-section { margin-top: 1rem; margin-bottom: 0.5rem; }
                .source-title { font-size: 1.6rem; padding-bottom: 6px; }
                .card { padding: 1rem; min-height: 120px; }
                .card h3 { font-size: 0.95rem; margin-bottom: 0.5rem; }
                .snippet { font-size: 0.8rem; margin-top: 0.3rem; }
                .card-footer { margin-top: 0.6rem; }
                .time { font-size: 0.65rem; }
                .like-button { font-size: 1.2rem; }
                footer { margin-top: 2rem; font-size: 0.75rem; padding-top: 0.8rem; }
                #scrollToTopBtn { bottom: 15px; right: 15px; padding: 10px; font-size: 14px; }
                .top-controls { margin-bottom: 1rem; padding: 0 0.5rem; }
            }
            @media (max-width: 480px) {
                .news-grid { grid-template-columns: 1fr; grid-gap: 10px; }
                .intro-message { padding: 0.5rem; font-size: 0.9rem; }
                h1 { font-size: 1.8rem; }
                .source-title { font-size: 1.4rem; }
            }
        </style>
        <meta http-equiv="refresh" content="3600" />
    </head>
    <body>
        <button onclick="topFunction()" id="scrollToTopBtn" title="Go to top">⬆️</button>

        <div class="top-controls">
            <h1 style="margin: 0;">🗞 Your Daily News </h1>
            <div class="toggle-container">
                <label id="darkModeToggleLabel">Dark Mode</label>
                <label class="switch">
                    <input type="checkbox" id="darkModeToggle">
                    <span class="slider round"></span>
                </label>
                <label class="switch">
                    <input type="checkbox" id="startupFilterToggle">
                    <span class="slider round"></span>
                </label>
                <label id="startupFilterToggleLabel">Show Startup</label>
            </div>
        </div>

        <div class="intro-message">
            <p>Welcome to your personalized news aggregator! Select articles you're interested in for a custom audio summary.</p>
        </div>

        <div class="podcast-controls">
            <label for="podcast-length">How much time do you have for the news summary?</label>
            <span id="time-display">10 seconds</span>
            <input type="range" id="podcast-length" min="5" max="15" value="10">
            <button onclick="generatePodcast()">Listen</button>
            <p>Tip: "Like" articles below to create a custom podcast from your selections!</p>
        </div>

        <div class="news-grid">
            {% for source_name, headlines in sorted_source_groups %}
            <div class="source-section" data-source-type="{{ headlines[0].news_type if headlines else 'general' }}">
                <h2 class="source-title">
                    {{ NEWS_CONFIG[headlines[0].news_type][source_name].icon if headlines and NEWS_CONFIG[headlines[0].news_type][source_name].icon else '' }}
                    {{ source_name }}
                </h2>
            </div>
            {% if headlines %}
                {% for headline in headlines %}
                <div class="card" data-article-id="{{ headline.id }}" data-news-type="{{ headline.news_type }}">
                    <h3><a href="{{ headline.link }}" target="_blank" rel="noopener noreferrer">{{ headline.title }}</a></h3>
                    <p class="snippet">{{ headline.snippet }}</p>
                    <div class="card-footer">
                        {% if headline.publish_time %}<span class="time">{{ headline.publish_time }}</span>{% endif %}
                        <button class="like-button" data-article-id="{{ headline.id }}">❤️</button>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="no-headlines" data-news-type="{{ NEWS_CONFIG['general'][source_name].news_type if source_name in NEWS_CONFIG['general'] else NEWS_CONFIG['startup'][source_name].news_type }}">
                    <p>No headlines could be fetched from {{ source_name }} at this time. This may be due to website structure changes or blocking.</p>
                </div>
            {% endif %}
            {% endfor %}
        </div>

        <footer>
            <p>
                Last updated: {{ datetime.now().strftime('%Y-%m-%d %H:%M:%S') }} BST
            </p>
        </footer>

        <script>
            const podcastLengthSlider = document.getElementById('podcast-length');
            const timeDisplay = document.getElementById('time-display');
            const likeButtons = document.querySelectorAll('.like-button');
            const likedArticleIds = new Set(); 
            const scrollToTopBtn = document.getElementById("scrollToTopBtn");
            const startupFilterToggle = document.getElementById('startupFilterToggle');
            const startupFilterToggleLabel = document.getElementById('startupFilterToggleLabel');
            const newsCards = document.querySelectorAll('.card');
            const sourceSections = document.querySelectorAll('.source-section');
            const noHeadlineDivs = document.querySelectorAll('.no-headlines');
            const darkModeToggle = document.getElementById('darkModeToggle');
            const body = document.body;

            // Initialize dark mode based on local storage or system preference
            if (localStorage.getItem('darkMode') === 'enabled' || (window.matchMedia('(prefers-color-scheme: dark)').matches && !localStorage.getItem('darkMode'))) {
                body.classList.add('dark-mode');
                darkModeToggle.checked = true;
            }

            darkModeToggle.addEventListener('change', () => {
                if (darkModeToggle.checked) {
                    body.classList.add('dark-mode');
                    localStorage.setItem('darkMode', 'enabled');
                } else {
                    body.classList.remove('dark-mode');
                    localStorage.setItem('darkMode', 'disabled');
                }
            });

            // Adjust time display for podcast length slider
            podcastLengthSlider.oninput = function() {
                const value = parseInt(this.value);
                let displayText = `${value} second${value !== 1 ? 's' : ''}`; 
                timeDisplay.innerHTML = displayText;
            }
            document.addEventListener('DOMContentLoaded', () => {
                podcastLengthSlider.oninput(); 
                // Initialize startup filter state
                updateNewsDisplay();
            });

            // Handle "Like" button clicks
            likeButtons.forEach(button => {
                button.addEventListener('click', () => {
                    const articleId = button.dataset.articleId;
                    const card = button.closest('.card'); 

                    if (likedArticleIds.has(articleId)) {
                        likedArticleIds.delete(articleId);
                        card.classList.remove('selected-card');
                        button.classList.remove('selected');
                    } else {
                        likedArticleIds.add(articleId);
                        card.classList.add('selected-card');
                        button.classList.add('selected');
                    }
                    console.log('Liked Articles:', Array.from(likedArticleIds));
                });
            });

            // Startup filter toggle logic
            startupFilterToggle.addEventListener('change', () => {
                updateNewsDisplay();
            });

            function updateNewsDisplay() {
                const showStartupOnly = startupFilterToggle.checked;
                startupFilterToggleLabel.textContent = showStartupOnly ? 'Show All' : 'Show Startup';

                newsCards.forEach(card => {
                    const newsType = card.dataset.newsType;
                    if (showStartupOnly) {
                        if (newsType === 'startup') {
                            card.style.display = 'flex'; // Show startup cards
                        } else {
                            card.style.display = 'none'; // Hide general cards
                        }
                    } else {
                        card.style.display = 'flex'; // Show all cards
                    }
                });

                sourceSections.forEach(section => {
                    const newsType = section.dataset.sourceType;
                    if (showStartupOnly) {
                        if (newsType === 'startup') {
                            section.style.display = 'block'; // Show startup source titles
                        } else {
                            section.style.display = 'none'; // Hide general source titles
                        }
                    } else {
                        section.style.display = 'block'; // Show all source titles
                    }
                });

                noHeadlineDivs.forEach(div => {
                    const newsType = div.dataset.newsType;
                    if (showStartupOnly) {
                        if (newsType === 'startup') {
                            div.style.display = 'block'; // Show startup specific no headlines
                        } else {
                            div.style.display = 'none'; // Hide general no headlines
                        }
                    } else {
                        div.style.display = 'block'; // Show all no headlines
                    }
                });
            }

            function generatePodcast() {
                const length = podcastLengthSlider.value;
                const likedIdsParam = Array.from(likedArticleIds).join(','); 
                const newsTypeFilter = startupFilterToggle.checked ? 'startup' : 'general'; // Pass the current filter state

                let url = `/podcast_script?length=${length}&news_type=${newsTypeFilter}`;
                if (likedIdsParam) {
                    url += '&liked_articles=' + encodeURIComponent(likedIdsParam);
                }
                window.location.href = url;
            }

            // Scroll to top button functionality
            window.onscroll = function() { scrollFunction() };

            function scrollFunction() {
                if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
                    scrollToTopBtn.style.display = "block";
                } else {
                    scrollToTopBtn.style.display = "none";
                }
            }
            function topFunction() {
                document.body.scrollTop = 0; 
                document.documentElement.scrollTop = 0; 
            }
        </script>
    </body>
    </html>
    ''', sorted_source_groups=sorted_source_groups, NEWS_CONFIG=NEWS_CONFIG, datetime=datetime)

@app.route('/podcast_script')
def podcast_script():
    length_seconds = request.args.get('length', type=int, default=10)
    news_type_filter = request.args.get('news_type', type=str, default='general') # Renamed for clarity
    liked_articles_param = request.args.get('liked_articles', type=str, default='')

    length_seconds = max(5, min(length_seconds, 15))

    liked_article_ids = set()
    if liked_articles_param:
        liked_article_ids = set(liked_articles_param.split(','))

    # Fetch all headlines, then filter by news_type_filter (if applicable) and liked articles
    all_fetched_headlines = fetch_all_news()

    # First, filter by news_type_filter if it's 'startup'
    if news_type_filter == 'startup':
        headlines_by_type = [h for h in all_fetched_headlines if h.get('news_type') == 'startup']
    else: # Default or 'general'
        headlines_by_type = [h for h in all_fetched_headlines if h.get('news_type') == 'general' or h.get('news_type') == 'startup'] # Include both for 'general' view


    # Then, apply liked articles filter if present, otherwise use all from the type filter
    if liked_article_ids:
        filtered_headlines_for_summary = [h for h in headlines_by_type if h.get('id') in liked_article_ids]
        if not filtered_headlines_for_summary: # Fallback if liked articles don't match or none liked
            print("Warning: No liked articles found or matched for podcast summary. Summarizing all available headlines for the selected type.")
            filtered_headlines_for_summary = headlines_by_type
    else:
        filtered_headlines_for_summary = headlines_by_type
        print("No articles liked. Summarizing all available headlines for the selected type.")


    if not filtered_headlines_for_summary:
        return render_template_string('''
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Podcast Summary</title>
                <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
                <style>
                    body { font-family: 'Montserrat', sans-serif; background: #f0f2f5; color: #333; margin: 0; padding: 2rem; line-height: 1.6; }
                    .podcast-script-container { max-width: 800px; margin: 2rem auto; background: #ffffff; padding: 2.5rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
                    .podcast-script-container h2 { text-align: center; color: #2c3e50; font-size: 2rem; margin-bottom: 1.5rem; }
                    .podcast-script-content { white-space: pre-wrap; font-size: 1.1rem; line-height: 1.8; color: #444; }
                    .back-button-container { text-align: center; margin-top: 2rem; }
                    .back-button { display: inline-block; padding: 10px 20px; background-color: #FF69B4; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; transition: background-color 0.2s ease; }
                    .back-button:hover { background-color: #FA8072; }
                </style>
            </head>
            <body>
                <div class="podcast-script-container">
                    <h2>Generated Podcast Summary</h2>
                    <p class="podcast-script-content">No headlines available to generate a podcast summary for the selected criteria. Please check the main news page.</p>
                    <div class="back-button-container">
                        <a href="/" class="back-button">Back</a>
                    </div>
                </div>
            </body>
            </html>
        ''')

    news_summary_text_list = []
    
    # Organize filtered headlines by source for the prompt
    sources_for_prompt = {}
    for headline in filtered_headlines_for_summary:
        source_name = headline['source_name']
        if source_name not in sources_for_prompt:
            sources_for_prompt[source_name] = []
        sources_for_prompt[source_name].append(headline)

    for source_name, headlines_list in sources_for_prompt.items():
        news_summary_text_list.append(f"--- {source_name} ---")
        for headline in headlines_list:
            news_summary_text_list.append(f"- Title: {headline['title']}")
            news_summary_text_list.append(f"  Snippet: {headline['snippet']}")
        news_summary_text_list.append("\n")


    length_display_text = f"{length_seconds} second{'s' if length_seconds != 1 else ''}" 

    summary_title_main = ""
    if news_type_filter == 'general':
        summary_title_main = "Your Daily Briefing (General News)"
    elif news_type_filter == 'startup':
        summary_title_main = "Your Startup Briefing"
    else: # This would be if no filter, or fallback
        summary_title_main = "Your Combined News Summary" 
    
    if liked_article_ids:
        summary_title_main = "Your Personalized Briefing"


    WORDS_PER_SECOND = 1.8 

    max_words_for_audio = length_seconds * WORDS_PER_SECOND

    prompt_text = (
        f"Generate a concise, engaging {summary_title_main} podcast summary designed to be read aloud by a host. "
        "The tone should be conversational, informative, and flow smoothly as if delivering a short broadcast. "
        "Focus on the key developments from the provided headlines and snippets. "
        "Ensure a clear introduction and a smooth sign-off, without mentioning specific sources or including external links. "
        f"Aim for a summary that can be read in approximately {length_display_text}. "
        "It should be extremely concise and to the point, limiting itself to the most important information to fit the strict time constraint. "
        "Be very brief. Here is the news:\n\n" + "\n".join(news_summary_text_list)
    )

    podcast_script_content = "" 
    try:
        chatHistory = [];
        chatHistory.append({"role": "user", "parts": [{"text": prompt_text}]} ); 
        payload = {"contents": chatHistory};
        apiKey = "AIzaSyCx9X9Jpi7qXNqq_7mJurI2wRaN3dPstXg" 
        apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={apiKey}";
        
        response = requests.post(apiUrl, headers={'Content-Type': 'application/json'}, data=json.dumps(payload), timeout=60)
        response.raise_for_status() 
        result = response.json()

        if result and result.get("candidates") and len(result["candidates"]) > 0 and \
           result["candidates"][0].get("content") and \
           result["candidates"][0]["content"].get("parts") and \
           len(result["candidates"][0]["content"]["parts"]) > 0:
            generated_text = result["candidates"][0]["content"]["parts"][0].get("text", "No summary text was generated by the AI.")
            
            words = generated_text.split()
            if len(words) > max_words_for_audio:
                podcast_script_content = " ".join(words[:int(max_words_for_audio)]) + "..."
            else:
                podcast_script_content = generated_text

        else:
            print(f"Gemini API response structure unexpected: {result}")
            podcast_script_content = "Could not parse AI response for the news summary. Please try again or check API key."

    except requests.exceptions.RequestException as e:
        print(f"Error calling Gemini API: {e}")
        podcast_script_content = f"Error communicating with AI to generate summary: {e}. Check API key and network."
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from Gemini API: {e}")
        podcast_script_content = f"Error processing AI response (JSON decode error): {e}. AI response might be malformed."
    except Exception as e:
        print(f"An unexpected error occurred during news summary generation: {e}")
        podcast_script_content = f"An unexpected error occurred: {e}. Please report this issue."

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Podcast Summary</title>
            <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
            <style>
                :root {
                    --primary-color: #FF69B4; /* Neon Pink */
                    --primary-hover-color: #FA8072; /* Slightly darker pink on hover */
                    --background-color: #f0f2f5;
                    --card-background: #ffffff;
                    --text-color: #333;
                    --heading-color: #1a1a1a;
                    --snippet-color: #555;
                    --time-color: #888;
                    --border-color: #e0e0e0;
                    --selected-border: var(--primary-color);
                    --selected-background: #ffe3f1; 
                    --error-color: #dc3545;

                    /* Dark Mode variables */
                    --dark-bg: #282c34;
                    --dark-card-bg: #3c414d;
                    --dark-text: #e0e0e0;
                    --dark-heading: #ffffff;
                    --dark-snippet: #bbbbbb;
                    --dark-time: #aaaaaa;
                    --dark-border: #4a505c;
                    --dark-podcast-controls-bg: #343a40;
                }

                body { 
                    font-family: 'Montserrat', sans-serif; 
                    background: var(--background-color); 
                    color: var(--text-color); 
                    margin: 0; 
                    padding: 2rem; 
                    line-height: 1.6;
                    transition: background-color 0.3s, color 0.3s;
                }
                body.dark-mode {
                    background: var(--dark-bg);
                    color: var(--dark-text);
                }
                body.dark-mode h2 {
                    color: var(--dark-heading);
                }
                body.dark-mode .podcast-script-content {
                    color: var(--dark-snippet);
                }
                body.dark-mode .audio-player-section {
                    background: var(--dark-card-bg);
                }


                .podcast-script-container { max-width: 800px; margin: 2rem auto; background: var(--card-background); padding: 2.5rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
                .podcast-script-container h2 { text-align: center; color: var(--heading-color); font-size: 2rem; margin-bottom: 1.5rem; }
                .podcast-script-content { white-space: pre-wrap; font-size: 1.1rem; line-height: 1.8; color: #444; }
                .back-button-container {
                    text-align: center;
                    margin-top: 2rem;
                }
                .back-button { 
                    padding: 10px 20px; 
                    background-color: var(--primary-color); 
                    color: white; 
                    text-decoration: none; 
                    border-radius: 8px; 
                    font-weight: 600; 
                    transition: background-color 0.2s ease; 
                    display: inline-block; 
                }
                .back-button:hover { 
                    background-color: var(--primary-hover-color); 
                }
                .audio-player-section {
                    text-align: center;
                    margin-top: 2rem;
                    padding: 1rem;
                    background-color: #f8f9fa;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                    display: flex; 
                    flex-direction: column;
                    align-items: center; 
                    justify-content: center;
                    max-width: 500px; 
                    margin-left: auto;
                    margin-right: auto;
                }
                #playAudioButton { 
                    padding: 12px 25px;
                    background-color: var(--primary-color); 
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 1.1rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background-color 0.2s ease, transform 0.1s ease;
                    box-shadow: 0 3px 6px rgba(0,0,0,0.15);
                    margin-bottom: 1rem; 
                }
                #playAudioButton:hover {
                    background-color: var(--primary-hover-color); 
                    transform: translateY(-1px);
                }
                #audioPlayer {
                    width: 80%;
                    max-width: 400px;
                    margin-top: 1rem;
                }
                #audio-message {
                    margin-top: 1rem;
                    color: var(--error-color); 
                    font-weight: bold;
                }
                #loading-spinner {
                    display: none; 
                    border: 4px solid rgba(0, 0, 0, 0.1);
                    border-top: 4px solid var(--primary-color); 
                    border-radius: 50%;
                    width: 24px;
                    height: 24px;
                    animation: spin 1s linear infinite;
                    margin: 1rem auto;
                }

                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        </head>
        <body>
            <div class="podcast-script-container">
                <h2>{{ summary_title_main }} ({{ length_display_text }})</h2>
                <p class="podcast-script-content" id="podcastScriptContent">{{ script_content }}</p>
                
                <div class="audio-player-section">
                    <button id="playAudioButton">Play</button> 
                    <div id="loading-spinner"></div>
                    <audio id="audioPlayer" controls></audio>
                    <p id="audio-message"></p>
                </div>

                <div class="back-button-container">
                    <a href="/" class="back-button">Back</a> 
                </div>
            </div>

            <script>
                const playAudioButton = document.getElementById('playAudioButton');
                const podcastScriptContent = document.getElementById('podcastScriptContent');
                const audioPlayer = document.getElementById('audioPlayer');
                const audioMessage = document.getElementById('audio-message');
                const loadingSpinner = document.getElementById('loading-spinner');
                const body = document.body;

                // Initialize dark mode based on local storage or system preference
                if (localStorage.getItem('darkMode') === 'enabled' || (window.matchMedia('(prefers-color-scheme: dark)').matches && !localStorage.getItem('darkMode'))) {
                    body.classList.add('dark-mode');
                }

                if (playAudioButton) {
                    playAudioButton.addEventListener('click', async () => {
                        const scriptText = podcastScriptContent.textContent;
                        audioPlayer.src = ''; 
                        audioMessage.textContent = ''; 
                        playAudioButton.disabled = true; 
                        loadingSpinner.style.display = 'block'; 

                        try {
                            const response = await fetch('/generate_audio', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({ script: scriptText })
                            });

                            if (!response.ok) {
                                const errorData = await response.json();
                                throw new Error(errorData.error || 'Failed to generate audio.');
                            }

                            const audioBlob = await response.blob();
                            const audioUrl = URL.createObjectURL(audioBlob);
                            audioPlayer.src = audioUrl;
                            audioPlayer.play();
                            audioMessage.textContent = 'Playing podcast!';

                        } catch (error) {
                            console.error('Error generating audio:', error);
                            audioMessage.textContent = `Error: ${error.message}`;
                        } finally {
                            playAudioButton.disabled = false; 
                            loadingSpinner.style.display = 'none'; 
                        }
                    });
                }
            </script>
        </body>
        </html>
    ''', script_content=podcast_script_content, length_display_text=length_display_text, news_type_filter=news_type_filter, summary_title_main=summary_title_main)

@app.route('/generate_audio', methods=['POST'])
def generate_audio():
    data = request.json
    script_text = data.get('script', '')

    if not script_text:
        return jsonify({"error": "No script text provided."}), 400

    # IMPORTANT: Replace "YOUR_ELEVENLABS_API_KEY" with your actual ElevenLabs API key.
    # Keep this key secure and do not commit it to public repositories.
    # For production, consider using environment variables.
    ELEVENLABS_API_KEY = "sk_700880ba061d379f43aaf20c865a358ee3643118a57df496" 

    if not ELEVENLABS_API_KEY:
        return jsonify({"error": "ElevenLabs API key not configured on the server."}), 500

    # ElevenLabs API endpoint for Text-to-Speech
    # Using a common voice_id (e.g., "Adam"). You can explore others via their API or website.
    # Using model_id 'eleven_turbo_v2_5' for good balance of quality and speed.
    url = "https://api.elevenlabs.io/v1/text-to-speech/56AoDkrOh6qfVPDXZ7Pt/stream" # Example voice ID
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY 
    }

    # ElevenLabs payload
    payload = {
        "text": script_text,
        "model_id": "eleven_turbo_v2_5", # A good balance of quality and speed
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

        audio_stream = io.BytesIO(response.content)
        
        # Send the audio data back as an audio file
        return send_file(
            audio_stream,
            mimetype="audio/mpeg",
            as_attachment=False, # Don't force download, allow browser to play
            download_name="podcast.mp3"
        )

    except requests.exceptions.RequestException as e:
        print(f"Error calling ElevenLabs API: {e}")
        return jsonify({"error": f"Error communicating with ElevenLabs: {e}"}), 500
    except Exception as e:
        print(f"An unexpected error occurred during audio generation: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
