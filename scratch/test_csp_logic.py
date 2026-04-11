import sys
import os

# Add scripts to path
sys.path.append(os.path.abspath('scripts'))
from tunnel_client import inject_csp_to_html

def test():
    html = b"<html><head><title>Test</title></head><body>Hello</body></html>"
    headers = {"Content-Type": "text/html; charset=UTF-8"}
    
    result = inject_csp_to_html(html, headers)
    print(f"Injection result: {result.decode()}")
    
    if b'upgrade-insecure-requests' in result:
        print("SUCCESS: CSP found in output")
    else:
        print("FAILURE: CSP missing")

    # Test Gzipped mock (should fail find, but we stripped accept-encoding so this shouldn't happen in real life)
    import gzip
    gz_html = gzip.compress(html)
    result_gz = inject_csp_to_html(gz_html, headers)
    if b'upgrade-insecure-requests' in result_gz:
        print("ERROR: Injected into gzip?!")
    else:
        print("OK: Ignored binary/gzip appropriately")

if __name__ == "__main__":
    test()
