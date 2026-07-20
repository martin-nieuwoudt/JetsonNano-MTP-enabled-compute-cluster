import urllib.request
try:
    print("HTTP", urllib.request.urlopen("https://huggingface.co", timeout=8).status)
except Exception as e:
    print("NODE_NO_INTERNET", e)
