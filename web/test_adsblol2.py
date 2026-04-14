import urllib.request

def test_headers(headers, desc):
    url = 'https://api.adsb.lol/0/me'
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            content = response.read()
            print(f"{desc}: SUCCESS {response.status}")
    except Exception as e:
        print(f"{desc}: ERROR {e}")

test_headers({'User-Agent': 'Mozilla/5.0'}, "Only User-Agent")
test_headers({'User-Agent': 'Mozilla/5.0', 'Referer': 'https://api.adsb.lol/0/me'}, "With Referer")
test_headers({'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip'}, "With GZIP")
test_headers({'User-Agent': 'Mozilla/5.0', 'Accept': '*/*'}, "With Accept */*")
