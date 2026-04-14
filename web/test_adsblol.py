import urllib.request
import gzip
import io

try:
    url = 'https://api.adsb.lol/0/me'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip',
        'Cache-Control': 'no-cache',
        'Referer': url
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        encoding = response.info().get('Content-Encoding')
        content = response.read()
        print(f"Status: 200, Encoding: {encoding}")
        if encoding == 'gzip':
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as f:
                content = f.read()
        print(f"Content length: {len(content)}")
except Exception as e:
    print(f"Error: {e}")
