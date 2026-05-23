import urllib.request
from smolagents.tools import Tool

class ReadUrlContentTool(Tool):
    name = "read_url_content"
    description = "Fetch content from a URL via HTTP request. Useful for reading documentation or static webpages."
    inputs = {
        "url": {
            "type": "string",
            "description": "URL to read content from."
        }
    }
    output_type = "string"

    def forward(self, url: str) -> str:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
            
            # Attempt to use markdownify if installed, otherwise basic strip
            try:
                from markdownify import markdownify
                return markdownify(html).strip()
            except ImportError:
                import re
                text = re.sub('<[^<]+?>', ' ', html)
                # compress whitespace
                text = re.sub(r'\s+', ' ', text)
                return text.strip()
        except Exception as e:
            import traceback
            return f"Error fetching URL {url}: {e}\n\nTraceback:\n{traceback.format_exc()}"
