import urllib.request

url = 'https://api.ipify.org?format=json'
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    print(response.read().decode('utf-8'))
