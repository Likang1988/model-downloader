"""Test hf-mirror API with exact code headers"""
import requests

DEFAULT_HEADERS = {
    "User-Agent": "ModelDownloader/1.0 (Windows; +https://github.com) Python/3.x",
    "Accept": "application/json",
}

mirror = True
base = "https://hf-mirror.com" if mirror else "https://huggingface.co"
repo_id = "moonshotai/Kimi-K2.7-Code"

# Test model type
print("=== Model type ===")
api_url = f"{base}/api/models/{repo_id}"
print(f"URL: {api_url}")
r = requests.get(api_url, timeout=15, headers=DEFAULT_HEADERS)
print(f"Status: {r.status_code}")
data = r.json()
siblings = data.get("siblings", [])
print(f"Siblings count: {len(siblings)}")
for s in siblings[:5]:
    print(f"  rfilename={s['rfilename']}, size={s.get('size', 0)}")

# Test dataset type
print()
print("=== Dataset type ===")
api_url2 = f"{base}/api/datasets/{repo_id}"
print(f"URL: {api_url2}")
r2 = requests.get(api_url2, timeout=15, headers=DEFAULT_HEADERS)
print(f"Status: {r2.status_code}")
if r2.status_code == 200:
    data2 = r2.json()
    siblings2 = data2.get("siblings", [])
    print(f"Siblings count: {len(siblings2)}")
else:
    print(f"Body: {r2.text[:200]}")
