"""Read external product metadata and check destination health, without tracking clicks.

Standalone server-side engine for LinKs tracked links. No database writes, tokens,
platform attribution or HTTP API endpoints live here. Both public operations share
an SSRF-resistant transport that pins each connection to a validated public IP.
"""

from __future__ import annotations

import html
from html.parser import HTMLParser
import http.client
import ipaddress
import json
import re
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import unquote, urljoin, urlsplit

MAX_URL = 2000
MAX_HTML = 256 * 1024
TIMEOUT = 3
MAX_REDIRECTS = 4
USER_AGENT = 'LinKs-URL-Inspector/1.0 (+metadata and availability check)'


class InspectionError(Exception):
    """An external URL could not safely or conclusively be inspected."""


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str = ''
    body: bytes = b''
    location: str = ''


@dataclass(frozen=True)
class Target:
    url: str
    host: str
    port: int
    path: str
    secure: bool


def _target(url):
    if not isinstance(url, str) or not url or len(url) > MAX_URL:
        raise InspectionError('URL invalide ou trop longue.')
    if any(ord(char) <= 32 or ord(char) == 127 for char in url) or '\\' in url:
        raise InspectionError('URL contenant des caractères interdits.')
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise InspectionError('Seules les URL HTTP(S) publiques sont autorisées.')
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == 'https' else 80)
        if port != (443 if parsed.scheme == 'https' else 80):
            raise InspectionError('Port non standard interdit pour la vérification.')
        host = parsed.hostname.rstrip('.').encode('idna').decode('ascii').lower()
    except (ValueError, UnicodeError) as exc:
        raise InspectionError('Adresse de destination invalide.') from exc
    if not host or len(host) > 253 or host in ('localhost',) or host.endswith(('.localhost', '.local', '.internal', '.invalid', '.test')):
        raise InspectionError('Destination locale ou réservée interdite.')
    try:
        literal = ipaddress.ip_address(host.strip('[]'))
        if not _global_ip(literal):
            raise InspectionError('Adresse IP non publique interdite.')
    except ValueError:
        if '.' not in host or any(not part for part in host.split('.')):
            raise InspectionError('Nom de domaine public requis.')
    path = (parsed.path or '/') + (('?' + parsed.query) if parsed.query else '')
    return Target(url, host, port, path, parsed.scheme == 'https')


def _global_ip(ip):
    if getattr(ip, 'ipv4_mapped', None):
        return ip.ipv4_mapped.is_global
    return ip.is_global


def _approved_ip(target, resolver):
    """Reject mixed private/public DNS replies, and pin the socket to one resolved IP."""
    try:
        answers = resolver(target.host, target.port, type=socket.SOCK_STREAM)
        addresses = [entry[4][0] for entry in answers]
        if not addresses or any(not _global_ip(ipaddress.ip_address(addr)) for addr in addresses):
            raise InspectionError('Résolution DNS non publique ou ambiguë.')
        return addresses[0]
    except (OSError, ValueError) as exc:
        raise InspectionError('Résolution DNS impossible ou non fiable.') from exc


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, ip, *, timeout):
        super().__init__(host, port, timeout=timeout)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, port, ip, *, timeout):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        try:
            # TLS certificate and SNI are checked against the hostname, not the IP.
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def _request_once(target, ip, method, max_bytes):
    connection = (_PinnedHTTPS if target.secure else _PinnedHTTP)(
        target.host, target.port, ip, timeout=TIMEOUT)
    try:
        connection.request(method, target.path, headers={
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.1' if method == 'GET' else '*/*',
            'Accept-Encoding': 'identity',
            'Connection': 'close',
        })
        response = connection.getresponse()
        body = response.read(max_bytes) if method == 'GET' else b''
        return Response(response.status, response.getheader('Content-Type', ''), body,
                        response.getheader('Location', ''))
    finally:
        connection.close()


def _fetch(url, *, method, max_bytes=0, requester=None, resolver=None):
    requester = requester or _request_once
    resolver = resolver or socket.getaddrinfo
    seen = set()
    for _ in range(MAX_REDIRECTS + 1):
        target = _target(url)
        if target.url in seen:
            raise InspectionError('Boucle de redirection.')
        seen.add(target.url)
        ip = _approved_ip(target, resolver)
        try:
            result = requester(target, ip, method, max_bytes)
        except (OSError, TimeoutError, ssl.SSLError, http.client.HTTPException) as exc:
            raise InspectionError('La destination ne répond pas de manière fiable.') from exc
        if not isinstance(result, Response):
            raise InspectionError('Réponse de vérification invalide.')
        if result.status in (301, 302, 303, 307, 308):
            if not result.location:
                raise InspectionError('Redirection sans destination.')
            url = urljoin(url, result.location)
            continue
        return result, target.url
    raise InspectionError('Trop de redirections.')


class _MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.title = []
        self.scripts = []
        self._in_title = False
        self._in_json = False
        self._script = []
        self._script_size = 0

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == 'meta':
            key = (fields.get('property') or fields.get('name') or '').lower()
            if key in {'og:title', 'twitter:title', 'product:brand', 'og:site_name'}:
                self.meta.setdefault(key, fields.get('content') or '')
        elif tag == 'title':
            self._in_title = True
        elif tag == 'script' and (fields.get('type') or '').lower().split(';')[0].strip() == 'application/ld+json':
            self._in_json = True
            self._script = []
            self._script_size = 0

    def handle_data(self, data):
        if self._in_title and len(''.join(self.title)) < 2000:
            self.title.append(data[:2000])
        if self._in_json and self._script_size < 128 * 1024:
            self._script.append(data[:128 * 1024 - self._script_size])
            self._script_size += len(data)

    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False
        if tag == 'script' and self._in_json:
            self.scripts.append(''.join(self._script))
            self._script = []
            self._in_json = False


def _product(obj, depth=0):
    if depth > 10:
        return None
    if isinstance(obj, list):
        for item in obj:
            found = _product(item, depth + 1)
            if found:
                return found
    if isinstance(obj, dict):
        types = obj.get('@type', '')
        is_product = lambda kind: isinstance(kind, str) and (kind == 'Product' or kind.endswith('/Product'))
        if (is_product(types) or isinstance(types, list) and any(is_product(t) for t in types)) and isinstance(obj.get('name'), str):
            brand = obj.get('brand')
            if isinstance(brand, dict):
                brand = brand.get('name', '')
            if not isinstance(brand, str):
                brand = ''
            return obj['name'], brand
        for value in (obj.get('@graph'), obj.get('mainEntity'), obj.get('itemListElement')):
            found = _product(value, depth + 1)
            if found:
                return found
    return None


_SHOP_PREFIX = re.compile(r'^(?:amazon(?:\.[a-z.]+)?|fnac|cdiscount|aliexpress|ebay(?:\.[a-z.]+)?)\s*[:|\-–]\s*', re.I)
_NOISE = re.compile(r'\b(?:livraison gratuite|expédition gratuite|free shipping|en promotion|meilleur prix|offre limitée|acheter maintenant)\b', re.I)
_SEPARATOR = re.compile(r'\s+[|–—·]\s+|\s+-\s+')


def clean_title(value, brand=''):
    """Conservative short label: preserve product model, never fabricate a brand."""
    if not isinstance(value, str):
        return ''
    value = html.unescape(re.sub(r'\s+', ' ', value)).strip(' \t\n\r-|–—·:')
    value = _SHOP_PREFIX.sub('', value)
    value = _SEPARATOR.split(value, 1)[0].strip()
    value = _NOISE.split(value, 1)[0].strip(' ,;:-')
    if brand and isinstance(brand, str) and brand.casefold() not in value.casefold():
        value = brand.strip() + ' ' + value
    # A short summary should not end in the middle of a reference or model.
    if len(value) > 60:
        head = value[:61].rsplit(' ', 1)[0].strip(' ,;:-')
        value = head if len(head) >= 8 else value[:60]
    return value if len(value) >= 3 else ''


def _slug_title(url):
    parts = [unquote(part) for part in urlsplit(url).path.split('/') if part]
    if not parts:
        return ''
    slug = parts[-1].rsplit('.', 1)[0] if parts[-1].endswith(('.html', '.htm')) else parts[-1]
    if slug.lower() in {'product', 'produit', 'item', 'p', 'dp', 'detail', 'details', 'exemple'}:
        return ''
    if re.fullmatch(r'[a-z0-9]{8,}', slug, re.I) and ('-' not in slug and '_' not in slug):
        return ''
    if not re.search(r'[a-zA-ZÀ-ÿ]', slug) or len(slug) < 7:
        return ''
    words = re.sub(r'[-_]+', ' ', slug).strip()
    if len(words.split()) < 2:
        return ''
    return clean_title(words)


def _slug_suggestion(url):
    title = _slug_title(url)
    return {'title': title, 'source': 'url_slug' if title else '',
            'status': 'ok' if title else 'unavailable'}


def suggest_title(url, *, requester=None, resolver=None):
    """Return {title, source, status}; title='' when no reliable suggestion exists.

    Fetching blocked pages is not fatal for creating a tracked link: the UI should
    leave the name editable and required. No remote data is persisted here.
    """
    try:
        _target(url)
    except InspectionError:
        return {'title': '', 'source': '', 'status': 'unavailable'}
    try:
        response, final_url = _fetch(url, method='GET', max_bytes=MAX_HTML,
                                      requester=requester, resolver=resolver)
        if not 200 <= response.status < 300 or not any(x in response.content_type.lower() for x in ('text/html', 'application/xhtml+xml')):
            return _slug_suggestion(final_url)
        encoding = 'utf-8'
        charset = re.search(r'charset\s*=\s*["\']?([\w-]+)', response.content_type, re.I)
        if charset:
            encoding = charset.group(1)
        try:
            page = response.body.decode(encoding, errors='replace')
        except LookupError:
            page = response.body.decode('utf-8', errors='replace')
        parser = _MetadataParser()
        parser.feed(page)
        for raw in parser.scripts[:8]:
            try:
                product = _product(json.loads(raw))
            except (ValueError, RecursionError, TypeError):
                continue
            if product:
                title = clean_title(*product)
                if title:
                    return {'title': title, 'source': 'schema_product', 'status': 'ok'}
        for source, candidate in (
            ('open_graph', parser.meta.get('og:title')),
            ('twitter', parser.meta.get('twitter:title')),
            ('html_title', ''.join(parser.title)),
            ('url_slug', _slug_title(final_url)),
        ):
            title = clean_title(candidate)
            if title:
                return {'title': title, 'source': source, 'status': 'ok'}
        return _slug_suggestion(final_url)
    except InspectionError:
        return _slug_suggestion(url)


def check_destination(url, *, requester=None, resolver=None):
    """Conservative outcome: valid / broken / unknown.

    Only a GET-confirmed 404/410 is broken; blocked robots, 5xx, TLS failures,
    timeouts and ambiguous redirects are unknown. Never calls a LinKs short URL.
    """
    try:
        response, _ = _fetch(url, method='HEAD', requester=requester, resolver=resolver)
        if 200 <= response.status < 300:
            return {'status': 'valid', 'http_status': response.status}
        # HEAD is unreliable on some shops; confirm negative statuses via GET.
        response, _ = _fetch(url, method='GET', max_bytes=0, requester=requester, resolver=resolver)
        if 200 <= response.status < 300:
            return {'status': 'valid', 'http_status': response.status}
        if response.status in (404, 410):
            return {'status': 'broken', 'http_status': response.status}
        return {'status': 'unknown', 'http_status': response.status}
    except InspectionError:
        return {'status': 'unknown', 'http_status': None}
