"""Generate a local publishing profile from GitHub Pages' public URL."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse

url = os.environ.get("SITE_URL", "").strip().rstrip("/")
parsed = urlparse(url)
if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
    raise SystemExit("SITE_URL must be the public HTTPS website base URL.")
Path("_quarto-publish.yml").write_text(
    json.dumps({"website": {"site-url": url + "/"}}, indent=2) + "\n",
    encoding="utf-8",
)
print("Publishing profile ready.")
