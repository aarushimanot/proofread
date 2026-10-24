"""
Importing reference passages for any topic.

A curator can add trusted sources to a topic in three ways:
  * paste a link  -> we download the page, keep the readable paragraphs and split them
                     into short passages (Wikipedia links use Wikipedia's own API for clean text)
  * paste text    -> the same splitting, without the download
  * type one passage by hand (handled directly by the API, no splitting)

Imports only produce a PREVIEW. Nothing is saved until the curator ticks the passages
they trust and presses save, so a human always decides what goes into the reference set.

Safety: only public http(s) addresses are fetched (no localhost or private network
addresses, also after redirects), with a size limit and a timeout.
"""
import ipaddress
import json
import re
import socket
import urllib.parse
import urllib.request
from datetime import date
from html.parser import HTMLParser

MAX_BYTES = 3_000_000          # stop reading pages larger than ~3 MB
TIMEOUT_SECONDS = 15
MAX_PASSAGES = 80              # cap per import so the preview stays manageable
SENTENCES_PER_PASSAGE = 3      # passages of 2-4 sentences match the built-in corpus
MIN_PASSAGE_WORDS = 12         # drop fragments such as captions or "Read more"
USER_AGENT = "ProofreadBot/1.0 (student claim-review prototype)"

# Wikipedia sections that are lists of links rather than facts.
SKIP_SECTIONS = {"references", "see also", "external links", "notes", "further reading",
                 "bibliography", "sources", "citations", "footnotes", "gallery"}


class ImportError_(Exception):
    """Raised with a message that is safe to show to the user."""


# ------------------------------------------------------------------ safe downloading
def _check_public(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ImportError_("Please enter a full web address starting with http:// or https://")
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        raise ImportError_(f"Could not find the website '{parsed.hostname}'. Check the link.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ImportError_("Only public websites can be imported.")


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_public(newurl)               # re-check every redirect target
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download(url: str) -> tuple[str, str]:
    """Return (final_url, text) for a public web page."""
    _check_public(url)
    opener = urllib.request.build_opener(_SafeRedirects)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype and "json" not in ctype and "text" not in ctype:
                raise ImportError_("That link isn't a web page (PDFs and images can't be imported yet). "
                                   "Copy the text and use 'Paste text' instead.")
            raw = resp.read(MAX_BYTES + 1)
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.geturl(), raw[:MAX_BYTES].decode(charset, errors="replace")
    except ImportError_:
        raise
    except Exception as exc:  # network errors, HTTP 403/404, timeouts...
        raise ImportError_(f"Could not download the page ({exc}). Some sites block automatic "
                           "downloads; copy the text and use 'Paste text' instead.")


# ------------------------------------------------------------------ Wikipedia
def _wikipedia(url: str) -> dict | None:
    """Use the Wikipedia API for clean article text, split by section."""
    parsed = urllib.parse.urlparse(url)
    m = re.match(r"^([a-z\-]+)(?:\.m)?\.wikipedia\.org$", parsed.hostname or "")
    if not m or not parsed.path.startswith("/wiki/"):
        return None
    lang, page = m.group(1), urllib.parse.unquote(parsed.path[len("/wiki/"):])
    api = (f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1"
           f"&redirects=1&format=json&titles={urllib.parse.quote(page)}")
    _, body = _download(api)
    pages = json.loads(body).get("query", {}).get("pages", {})
    article = next(iter(pages.values()), {})
    if "extract" not in article or not article["extract"].strip():
        raise ImportError_("Wikipedia has no article at that address.")
    title = article.get("title", page.replace("_", " "))

    sections, current, lines = [], None, []
    for line in article["extract"].splitlines():
        heading = re.match(r"^(=+)\s*(.+?)\s*\1$", line.strip())
        if heading:
            sections.append((current, "\n".join(lines)))
            current, lines = heading.group(2), []
        else:
            lines.append(line)
    sections.append((current, "\n".join(lines)))
    sections = [(s, t) for s, t in sections if t.strip() and (s or "").lower() not in SKIP_SECTIONS]
    return {"title": title, "source": "Wikipedia", "url": f"https://{lang}.wikipedia.org/wiki/{page}",
            "sections": sections}


# ------------------------------------------------------------------ any other web page
class _ParagraphParser(HTMLParser):
    """Collect paragraph text (grouped under the nearest heading) and basic metadata."""
    SKIP = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg", "figure"}

    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.in_p = self.in_heading = self.in_title = False
        self.buffer: list[str] = []
        self.sections: list[tuple[str | None, list[str]]] = [(None, [])]
        self.meta: dict[str, str] = {}
        self.page_title = ""
        self.h1 = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag == "meta":
            key = attrs.get("property") or attrs.get("name") or ""
            if key in {"og:site_name", "og:title", "article:published_time", "date", "dc.date"}:
                self.meta[key] = attrs.get("content", "")
        elif tag == "title":
            self.in_title = True
        elif self.skip_depth == 0 and tag == "p":
            self.in_p, self.buffer = True, []
        elif self.skip_depth == 0 and tag in {"h1", "h2", "h3"}:
            self.in_heading, self.buffer = True, []

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "title":
            self.in_title = False
        elif tag == "p" and self.in_p:
            self.in_p = False
            text = " ".join("".join(self.buffer).split())
            if text:
                self.sections[-1][1].append(text)
        elif tag in {"h1", "h2", "h3"} and self.in_heading:
            self.in_heading = False
            heading = " ".join("".join(self.buffer).split())
            if tag == "h1" and not self.h1:
                self.h1 = heading
            elif heading:
                self.sections.append((heading, []))

    def handle_data(self, data):
        if self.in_title:
            self.page_title += data
        if self.skip_depth == 0 and (self.in_p or self.in_heading):
            self.buffer.append(data)


def _generic_page(url: str) -> dict:
    final_url, html = _download(url)
    parser = _ParagraphParser()
    parser.feed(html)
    host = (urllib.parse.urlparse(final_url).hostname or "").removeprefix("www.")
    title = parser.meta.get("og:title") or parser.h1 or parser.page_title.strip() or host
    published = parser.meta.get("article:published_time") or parser.meta.get("date") or parser.meta.get("dc.date") or ""
    sections = [(s, "\n".join(paras)) for s, paras in parser.sections if paras]
    if not sections:
        raise ImportError_("No readable paragraphs were found on that page. "
                           "Copy the text and use 'Paste text' instead.")
    return {"title": title.strip(), "source": parser.meta.get("og:site_name") or host, "url": final_url,
            "date": published[:10], "sections": sections}


# ------------------------------------------------------------------ splitting into passages
def _clean(text: str) -> str:
    text = re.sub(r"\[\d+\]|\[citation needed\]|\[[a-z]\]", "", text)   # footnote markers
    return re.sub(r"\s+", " ", text).strip()


def split_into_passages(nlp, sections: list[tuple[str | None, str]], title: str) -> tuple[list[dict], bool]:
    """
    Turn (section heading, text) pairs into short passages of ~3 sentences.
    Passages never cross a section boundary, and each gets a title like
    "Article title: Section". Returns (passages, truncated?).
    """
    passages = []
    for section, text in sections:
        sentences = [s.text.strip() for s in nlp(_clean(text)).sents if len(s.text.split()) >= 3]
        for i in range(0, len(sentences), SENTENCES_PER_PASSAGE):
            chunk = " ".join(sentences[i:i + SENTENCES_PER_PASSAGE])
            if len(chunk.split()) < MIN_PASSAGE_WORDS:
                continue
            passages.append({"title": f"{title}: {section}" if section else title, "text": chunk})
            if len(passages) >= MAX_PASSAGES:
                return passages, True
    return passages, False


def preview_from_url(nlp, url: str) -> dict:
    url = url.strip()
    page = _wikipedia(url) or _generic_page(url)
    passages, truncated = split_into_passages(nlp, page["sections"], page["title"])
    if not passages:
        raise ImportError_("The page was downloaded but no usable passages were found.")
    retrieved = date.today().isoformat()
    return {
        "title": page["title"], "source": page["source"], "url": page["url"],
        "date": page.get("date") or retrieved, "truncated": truncated,
        "passages": [{**p, "source": page["source"], "url": page["url"],
                      "date": page.get("date") or retrieved} for p in passages],
    }


def preview_from_text(nlp, text: str, title: str, source: str, url: str = "", when: str = "") -> dict:
    sections = [(None, para) for para in re.split(r"\n\s*\n", text) if para.strip()]
    passages, truncated = split_into_passages(nlp, sections, title.strip())
    if not passages:
        raise ImportError_(f"The text is too short. Each passage needs at least {MIN_PASSAGE_WORDS} words.")
    when = when or date.today().isoformat()
    return {
        "title": title, "source": source, "url": url, "date": when, "truncated": truncated,
        "passages": [{**p, "source": source, "url": url, "date": when} for p in passages],
    }
