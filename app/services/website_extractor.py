"""Website extraction and HTML processing service."""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, Comment
import httpx

from app.config import settings


class WebsiteExtractionException(Exception):
    """Raised when website fetching or parsing fails."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ExtractedWebsiteData:
    """Container for parsed and structured website content."""

    def __init__(
        self,
        url: str,
        final_url: str,
        title: str,
        meta_description: str,
        og_data: Dict[str, str],
        headings: Dict[str, List[str]],
        navigation_links: List[str],
        main_text: str,
        status_code: int
    ):
        self.url = url
        self.final_url = final_url
        self.title = title
        self.meta_description = meta_description
        self.og_data = og_data
        self.headings = headings
        self.navigation_links = navigation_links
        self.main_text = main_text
        self.status_code = status_code

    def to_llm_context(self, max_length: int = 25000) -> str:
        """Format the extracted website data into a rich, token-efficient text prompt for the LLM."""
        h1s = ", ".join(self.headings.get("h1", [])) or "None"
        h2s = "; ".join(self.headings.get("h2", [])[:15]) or "None"
        h3s = "; ".join(self.headings.get("h3", [])[:20]) or "None"
        nav_items = ", ".join(self.navigation_links[:25]) or "None"

        # Truncate main text if necessary while keeping high value sections
        trimmed_body = self.main_text[:max_length]

        context = (
            f"--- WEBSITE CONTENT EXTRACTION ---\n"
            f"URL: {self.final_url}\n"
            f"TITLE: {self.title}\n"
            f"META DESCRIPTION: {self.meta_description}\n"
            f"OPEN GRAPH SITE NAME: {self.og_data.get('og:site_name', 'N/A')}\n"
            f"OPEN GRAPH TITLE: {self.og_data.get('og:title', 'N/A')}\n"
            f"OPEN GRAPH DESCRIPTION: {self.og_data.get('og:description', 'N/A')}\n"
            f"PRIMARY HEADINGS (H1): {h1s}\n"
            f"SUBHEADINGS (H2): {h2s}\n"
            f"SECONDARY HEADINGS (H3): {h3s}\n"
            f"NAVIGATION / MENU LINKS: {nav_items}\n\n"
            f"PAGE BODY TEXT:\n{trimmed_body}\n"
            f"--- END OF WEBSITE CONTENT ---"
        )
        return context


class WebsiteExtractor:
    """Fetches, cleans, and structures content from websites."""

    def __init__(self, timeout: int = settings.REQUEST_TIMEOUT, user_agent: str = settings.USER_AGENT):
        self.timeout = timeout
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        }

    async def extract(self, url: str) -> ExtractedWebsiteData:
        """Fetch URL asynchronously, parse HTML, and return structured website data."""
        try:
            async with httpx.AsyncClient(
                headers=self.headers,
                timeout=httpx.Timeout(self.timeout, connect=8.0),
                follow_redirects=True,
                max_redirects=settings.MAX_REDIRECTS,
                verify=True
            ) as client:
                response = await client.get(url)

        except httpx.ConnectTimeout:
            raise WebsiteExtractionException(
                f"Connection timed out while connecting to {url}. The server took too long to respond.",
                status_code=504
            )
        except httpx.ReadTimeout:
            raise WebsiteExtractionException(
                f"Read timed out while receiving data from {url}.",
                status_code=504
            )
        except httpx.ConnectError as exc:
            raise WebsiteExtractionException(
                f"Failed to connect to {url}. The host may be down or unreachable: {str(exc)}",
                status_code=502
            )
        except httpx.TooManyRedirects:
            raise WebsiteExtractionException(
                f"Too many redirects encountered while fetching {url}.",
                status_code=400
            )
        except httpx.HTTPError as exc:
            raise WebsiteExtractionException(
                f"HTTP network error when accessing {url}: {str(exc)}",
                status_code=502
            )
        except Exception as exc:
            raise WebsiteExtractionException(
                f"Unexpected error fetching {url}: {str(exc)}",
                status_code=500
            )

        # Validate HTTP status
        if response.status_code >= 400:
            if response.status_code == 404:
                raise WebsiteExtractionException(f"Website returned 404 Not Found at {url}.", status_code=404)
            elif response.status_code == 403:
                raise WebsiteExtractionException(f"Access forbidden (403) by website server at {url}.", status_code=403)
            else:
                raise WebsiteExtractionException(
                    f"Website returned HTTP status {response.status_code} at {url}.",
                    status_code=response.status_code
                )

        # Validate Content-Type
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            # Check if response text looks like HTML anyway
            if not ("<html" in response.text.lower() or "<body" in response.text.lower()):
                raise WebsiteExtractionException(
                    f"Unsupported content type '{content_type}'. The URL must point to an HTML webpage.",
                    status_code=415
                )

        return self._parse_html(url, str(response.url), response.text, response.status_code)

    def _parse_html(self, original_url: str, final_url: str, html_content: str, status_code: int) -> ExtractedWebsiteData:
        """Parse raw HTML with BeautifulSoup and extract high-value metadata and body text."""
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Remove non-content elements
        for element in soup(["script", "style", "noscript", "svg", "canvas", "iframe", "template", "form"]):
            element.decompose()

        # Remove HTML comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # 2. Extract Title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # 3. Extract Meta Description & OpenGraph Tags
        meta_description = ""
        og_data: Dict[str, str] = {}

        for meta in soup.find_all("meta"):
            name = meta.get("name", "").lower()
            prop = meta.get("property", "").lower()
            content = meta.get("content", "").strip()

            if not content:
                continue

            if name == "description" and not meta_description:
                meta_description = content

            if prop.startswith("og:"):
                og_data[prop] = content

        if not meta_description and "og:description" in og_data:
            meta_description = og_data["og:description"]

        if not title and "og:title" in og_data:
            title = og_data["og:title"]

        # 4. Extract Headings Hierarchy
        headings = {
            "h1": [h.get_text(separator=" ", strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)],
            "h2": [h.get_text(separator=" ", strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)],
            "h3": [h.get_text(separator=" ", strip=True) for h in soup.find_all("h3") if h.get_text(strip=True)],
        }

        # 5. Extract Navigation / Service links
        navigation_links = []
        for nav in soup.find_all(["nav", "header"]):
            for a in nav.find_all("a"):
                text = a.get_text(strip=True)
                if text and len(text) < 40 and text not in navigation_links:
                    navigation_links.append(text)

        # 6. Extract and clean main body text
        # Target main content containers if present
        main_container = soup.find(["main", "article", "div[role='main']", "div#content"]) or soup.body or soup

        raw_text = main_container.get_text(separator="\n", strip=True)

        # Normalize whitespace and excessive newlines
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)

        # Deduplicate consecutive identical lines (often caused by navigation breadcrumbs)
        deduped_lines = []
        for line in cleaned_text.splitlines():
            if not deduped_lines or line != deduped_lines[-1]:
                deduped_lines.append(line)
        cleaned_text = "\n".join(deduped_lines)

        # Fallback title if completely empty
        if not title:
            title = original_url

        return ExtractedWebsiteData(
            url=original_url,
            final_url=final_url,
            title=title,
            meta_description=meta_description,
            og_data=og_data,
            headings=headings,
            navigation_links=navigation_links,
            main_text=cleaned_text,
            status_code=status_code
        )
