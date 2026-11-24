import urllib.request
import urllib.parse
import re
import json

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
queries = [
    ('Coach Ali', 'Coach Ali El Clasico'),
    ('NOT YOUR TYPE', 'Not Your Type Indian street food'),
    ('Sony Sports Network', 'Sony Sports Network cricket highlights'),
    ('The Infographics Show', 'The Infographics Show')
]

for name, q in queries:
    url = f'https://www.youtube.com/results?search_query={urllib.parse.quote(q)}'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            vids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
            # Remove duplicates preserving order
            seen = set()
            unique_vids = [x for x in vids if not (x in seen or seen.add(x))]
            print(f'=== {name} ===')
            print('Top video IDs:', unique_vids[:3])
            for vid in unique_vids[:2]:
                thumb_url = f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg'
                print(f'  {vid}: {thumb_url}')
    except Exception as e:
        print(f'Error for {name}: {e}')
