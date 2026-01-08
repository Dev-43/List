import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from googlesearch import search
import sys
import re

def extract_wiki_infobox(soup, category_type='general'):
    """Extracts Director, Year, and Sequel info from Wikipedia Infobox."""
    data = {'director': None, 'year': None, 'sequel_prequel': None}
    
    infobox = soup.find('table', class_='infobox')
    if not infobox:
        return data

    rows = infobox.find_all('tr')
    for row in rows:
        header = row.find('th')
        if not header:
            continue
        header_text = header.get_text(strip=True).lower()
        
        # 1. Director / Author
        if category_type == 'read':
             if any(keyword in header_text for keyword in ['author', 'writer', 'created by']):
                data['director'] = row.find('td').get_text(strip=True) # Storing Author in director column for now
        else:
            if any(keyword in header_text for keyword in ['directed by', 'director', 'created by']):
                data['director'] = row.find('td').get_text(strip=True)

        # 2. Year (Release Date or Publication Date)
        if any(keyword in header_text for keyword in ['release date', 'published', 'publication date']):
             # Extract just the year if possible
             cell_text = row.find('td').get_text(strip=True)
             match = re.search(r'\d{4}', cell_text)
             if match:
                 data['year'] = match.group(0)
        
        # 3. Sequel / Prequel
        if any(keyword in header_text for keyword in ['followed by', 'preceded by', 'next']):
             data['sequel_prequel'] = row.find('td').get_text(strip=True)

    print(f"DEBUG: Extracted Wiki Data: {data}", file=sys.stderr)
    return data

def fetch_meta_data(query, category_type='general', category_name=''):
    query = query.strip()
    original_query = query
    
    # Context logic reinstated per user request
    context_keywords = ""
    cat_name_lower = category_name.lower()
    
    if category_type == 'read':
        if 'manga' in cat_name_lower:
            context_keywords = " manga"
        elif 'comic' in cat_name_lower:
             context_keywords = " comic"
        else:
            context_keywords = " novel book"
            
    elif category_type == 'watch':
        if 'anime' in cat_name_lower:
            context_keywords = " anime"
        elif 'series' in cat_name_lower or 'show' in cat_name_lower:
             context_keywords = " tv series"
        else:
            context_keywords = " film movie"
        
    print(f"DEBUGGING: Query='{query}', Type='{category_type}', List='{category_name}'", file=sys.stderr)
    
    # Only append if not a URL and keywords not already present (basic check)
    if not re.match(r'^https?://', query):
        clean_check = query.lower()
        should_append = True
        
        # Check if context already exists in query to avoid duplication
        # Simple check: if any word from context is in query, skip? 
        # Better: Check specific main keywords
        if category_type == 'read':
             if 'book' in clean_check or 'novel' in clean_check or 'manga' in clean_check or 'comic' in clean_check:
                 should_append = False
        elif category_type == 'watch':
             if 'movie' in clean_check or 'film' in clean_check or 'series' in clean_check or 'anime' in clean_check:
                 should_append = False
                 
        if should_append and context_keywords:
             print(f"DEBUG: Appending context: '{context_keywords}'", file=sys.stderr)
             query = f"{query}{context_keywords}"
        else:
             print(f"DEBUG: Context skipped (already present or none)", file=sys.stderr)
    
    target_url = None
    print(f"DEBUG: Final Processing query: {query}", file=sys.stderr)
    
    # 1. Determine URL
    if not re.match(r'^https?://', original_query):
        
        # Priority 1: DuckDuckGo Search (Robust, handles typos)
        try:
            print(f"DEBUG: Searching via DuckDuckGo (DDGS) for: {query}", file=sys.stderr)
            # Iterate more results to find relevant one
            ddgs_gen = DDGS().text(query, region='us-en', max_results=5)
            found_candidate = None
            
            for res in ddgs_gen:
                href = res.get('href', '')
                print(f"DEBUG: DDGS Candidate: {href}", file=sys.stderr)
                
                # Check for high quality sources
                if 'wikipedia.org' in href:
                    target_url = href
                    break
                elif 'imdb.com' in href or 'themoviedb.org' in href:
                    if not target_url: target_url = href # Keep as backup if no wiki found yet
                elif 'myanimelist.net' in href or 'kitsu.io' in href:
                     if not target_url: target_url = href
                elif not target_url:
                     # Store first result as last resort
                     found_candidate = href
            
            # If no specific high-quality match, use the first candidate
            if not target_url and found_candidate:
                target_url = found_candidate
                print("DEBUG: Using generic first result from DDGS", file=sys.stderr)
                
            if target_url:
                print(f"DEBUG: Selected URL via DDGS: {target_url}", file=sys.stderr)

        except Exception as e:
            print(f"DEBUG: DDGS Search failed: {e}", file=sys.stderr)

        # Priority 2: Google Search (Legacy/Backup - often blocked)
        if not target_url:
            try:
                print("DEBUG: Searching Google (Backup)...", file=sys.stderr)
                # Note: googlesearch.search returns a generator
                for j in search(query, num_results=5, sleep_interval=1, lang="en"):
                    if 'wikipedia.org' in j or 'imdb.com' in j:
                         target_url = j
                         break
                    if not target_url: target_url = j
                
                if target_url:
                     print(f"DEBUG: Found URL via Google: {target_url}", file=sys.stderr)

            except Exception as e:
                print(f"DEBUG: Google Search failed ({e}).", file=sys.stderr)

        # Priority 3: Wikipedia Guess
        if not target_url:
             wiki_url = f"https://en.wikipedia.org/wiki/{original_query.title().replace(' ', '_')}"
             print(f"DEBUG: Guessing Wikipedia URL: {wiki_url}", file=sys.stderr)
             try:
                 if requests.get(wiki_url, timeout=5).status_code == 200:
                    target_url = wiki_url
             except: pass
    
    if not target_url:
        return {'name': original_query, 'info': '', 'link': '', 'image_url': None, 'director':None, 'year':None, 'sequel_prequel':None}
        
    # 2. Scrape Meta
    try:
        print(f"DEBUG: Scrape URL: {target_url}", file=sys.stderr)
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(target_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')

        # 3. Extract Basic Data
        title = soup.title.string if soup.title else original_query
        # Clean Title (Remove " - Wikipedia", " - IMDb", etc.)
        title = re.sub(r' - Wikipedia.*', '', title)
        title = re.sub(r' - IMDb.*', '', title)
        
        description = ""
        meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        if meta_desc:
            description = meta_desc.get('content', '')
        
        # Image
        image_url = None
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image:
             image_url = og_image.get('content')
        
        # 4. Extract Rich Data (Wikipedia Specific)
        rich_data = {'director': None, 'year': None, 'sequel_prequel': None}
        if 'wikipedia.org' in target_url:
            rich_data = extract_wiki_infobox(soup, category_type=category_type)
            print(f"DEBUG: Extracted Wiki Data: {rich_data}", file=sys.stderr)

        print(f"DEBUG: Scraped - Title: {title}, Image: {bool(image_url)}", file=sys.stderr)

        return {
            'name': str(title).strip()[:100], 
            'info': str(description).strip()[:500], 
            'link': target_url,
            'image_url': image_url,
            'director': rich_data['director'],
            'year': rich_data['year'],
            'sequel_prequel': rich_data['sequel_prequel']
        }
    except Exception as e:
        print(f"DEBUG: Fetch/Parse Error: {e}", file=sys.stderr)
        # CRITICAL FIX: Return original_query on error, NOT the modified 'query'
        return {'name': original_query, 'info': '', 'link': target_url, 'image_url': None, 'director':None, 'year':None, 'sequel_prequel':None}
