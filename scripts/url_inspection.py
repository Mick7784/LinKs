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
import time
import queue
import threading
import unicodedata
from itertools import islice
from dataclasses import dataclass
from urllib.parse import unquote, urljoin, urlsplit

MAX_URL = 2000
MAX_HTML = 256 * 1024
TIMEOUT = 3
MAX_REDIRECTS = 4
TOTAL_TIMEOUT = 12
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
        return _global_ip(ip.ipv4_mapped)
    return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_unspecified)


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
        self.sock = sock
        try:
            # TLS certificate and SNI are checked against the hostname, not the IP.
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def _request_once(target, ip, method, max_bytes, *, deadline=None):
    deadline = deadline or time.monotonic() + TOTAL_TIMEOUT
    connection = (_PinnedHTTPS if target.secure else _PinnedHTTP)(
        target.host, target.port, ip, timeout=min(TIMEOUT, _remaining(deadline)))
    response = None
    def abort():
        sock = connection.sock or getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
    watchdog = threading.Timer(_remaining(deadline), abort)
    watchdog.daemon = True
    watchdog.start()
    try:
        connection.request(method, target.path, headers={
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.1' if method == 'GET' else '*/*',
            'Accept-Encoding': 'identity',
            'Connection': 'close',
        })
        response = connection.getresponse()
        body = b''
        if method == 'GET' and max_bytes and response.status not in (301, 302, 303, 307, 308):
            if response.getheader('Content-Encoding', 'identity').lower() not in ('', 'identity'):
                raise InspectionError('Encodage compressé non pris en charge.')
            length = response.getheader('Content-Length', '')
            if length.isdigit() and int(length) > max_bytes:
                raise InspectionError('Page trop volumineuse.')
            while len(body) <= max_bytes:
                # read1 avoids waiting for the entire body; bound every socket read.
                sock = connection.sock or getattr(getattr(response.fp, 'raw', None), '_sock', None)
                if sock:
                    sock.settimeout(min(TIMEOUT, _remaining(deadline)))
                block = response.read1(min(16384, max_bytes + 1 - len(body)))
                if not block:
                    break
                body += block
            if len(body) > max_bytes:
                raise InspectionError('Page trop volumineuse.')
        return Response(response.status, response.getheader('Content-Type', ''), body,
                        response.getheader('Location', ''))
    finally:
        watchdog.cancel()
        if response is not None:
            response.close()
        connection.close()


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise InspectionError('Délai global de récupération dépassé.')
    return remaining


# DNS has no portable socket timeout. Limit outstanding resolver workers as well
# as caller wait time, so stalled DNS cannot accumulate unbounded threads.
_DNS_SLOTS = threading.BoundedSemaphore(8)


def _resolve_before_deadline(target, resolver, deadline):
    if not _DNS_SLOTS.acquire(blocking=False):
        raise InspectionError('Résolution DNS occupée.')
    result = queue.Queue(maxsize=1)
    def resolve():
        try:
            result.put((True, _approved_ip(target, resolver)))
        except Exception as exc:
            result.put((False, exc))
        finally:
            _DNS_SLOTS.release()
    threading.Thread(target=resolve, daemon=True).start()
    try:
        ok, value = result.get(timeout=min(TIMEOUT, _remaining(deadline)))
    except queue.Empty as exc:
        raise InspectionError('Délai DNS dépassé.') from exc
    if not ok:
        raise value
    return value


def _fetch(url, *, method, max_bytes=0, requester=None, resolver=None, url_validator=None):
    requester = requester or _request_once
    resolver = resolver or socket.getaddrinfo
    seen = set()
    deadline = time.monotonic() + TOTAL_TIMEOUT
    for _ in range(MAX_REDIRECTS + 1):
        _remaining(deadline)
        target = _target(url)
        if url_validator is not None and not url_validator(target.url):
            raise InspectionError('Destination exclue de la vérification.')
        if target.url in seen:
            raise InspectionError('Boucle de redirection.')
        seen.add(target.url)
        ip = _resolve_before_deadline(target, resolver, deadline)
        try:
            result = (requester(target, ip, method, max_bytes, deadline=deadline)
                      if requester is _request_once else requester(target, ip, method, max_bytes))
        except (OSError, TimeoutError, ssl.SSLError, http.client.HTTPException, UnicodeError) as exc:
            raise InspectionError('La destination ne répond pas de manière fiable.') from exc
        if not isinstance(result, Response):
            raise InspectionError('Réponse de vérification invalide.')
        _remaining(deadline)
        if len(result.body) > max_bytes and max_bytes:
            raise InspectionError('Page trop volumineuse.')
        if result.status in (301, 302, 303, 307, 308):
            if not result.location:
                raise InspectionError('Redirection sans destination.')
            try:
                url = urljoin(url, result.location)
            except ValueError as exc:
                raise InspectionError('Destination de redirection invalide.') from exc
            continue
        return result, target.url
    raise InspectionError('Trop de redirections.')


class _MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.title = []
        self.headings = []
        self.product_names = []
        self.brands = []
        self.scripts = []
        self._captures = []
        self._in_json = False
        self._script = []
        self._script_size = 0

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        for capture in self._captures:
            if capture[0] == tag:
                capture[2] += 1
        if tag == 'meta':
            key = (fields.get('property') or fields.get('name') or '').lower()
            if key in {'og:title', 'twitter:title', 'product:brand', 'og:site_name'}:
                self.meta.setdefault(key, fields.get('content') or '')
        if tag == 'title':
            self._captures.append([tag, self.title, 1])
        elif tag == 'h1' or fields.get('id') == 'productTitle':
            capture = []
            (self.product_names if fields.get('id') == 'productTitle' else self.headings).append(capture)
            self._captures.append([tag, capture, 1])
        elif fields.get('itemprop') == 'brand':
            capture = [fields['content']] if fields.get('content') else []
            self.brands.append(capture)
            if tag != 'meta':
                self._captures.append([tag, capture, 1])
        if tag == 'script' and (fields.get('type') or '').lower().split(';')[0].strip() == 'application/ld+json':
            self._in_json = True
            self._script = []
            self._script_size = 0

    def handle_data(self, data):
        for _, capture, _ in self._captures:
            if sum(map(len, capture)) < 2000:
                capture.append(data[:2000])
        if self._in_json and self._script_size < 128 * 1024:
            self._script.append(data[:128 * 1024 - self._script_size])
            self._script_size += len(data)

    def handle_endtag(self, tag):
        # Close only the latest matching capture (nested spans remain harmless).
        for index in range(len(self._captures) - 1, -1, -1):
            if self._captures[index][0] == tag:
                self._captures[index][2] -= 1
                if self._captures[index][2] == 0:
                    del self._captures[index]
        if tag == 'script' and self._in_json:
            self.scripts.append(''.join(self._script))
            self._script = []
            self._in_json = False


def _structured(obj, depth=0):
    """Walk page entities, never recommendations/item lists or arbitrary objects."""
    if depth > 10:
        return
    if isinstance(obj, list):
        for item in obj[:32]:
            yield from _structured(item, depth + 1)
    if not isinstance(obj, dict):
        return
    kinds = obj.get('@type', [])
    kinds = kinds if isinstance(kinds, list) else [kinds]
    kinds = {kind.rstrip('/').rsplit('/', 1)[-1] for kind in kinds if isinstance(kind, str)}
    if 'Product' in kinds and isinstance(obj.get('name'), str):
        brand = obj.get('brand', '')
        if isinstance(brand, dict):
            brand = brand.get('name', '')
        model = obj.get('model', '')
        if isinstance(model, dict):
            model = model.get('name', '')
        yield ('schema_product', obj['name'], brand if isinstance(brand, str) else '',
               model if isinstance(model, str) else '')
    elif kinds & {'Article', 'NewsArticle', 'BlogPosting', 'VideoObject'}:
        yield ('schema_content', obj.get('headline') or obj.get('name'), '', '')
    elif 'ProfilePage' in kinds:
        person = obj.get('mainEntity')
        if isinstance(person, dict) and isinstance(person.get('name'), str):
            yield ('schema_profile', person['name'], '', '')
    for key in ('@graph', 'mainEntity'):
        yield from _structured(obj.get(key), depth + 1)


def _normal(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))


_STOP = {'de', 'du', 'des', 'le', 'la', 'les', 'un', 'une', 'et', 'a', 'au', 'aux', 'avec', 'pour',
         'the', 'and', 'with', 'for', 'of', 'on', 'sur'}


def _tokens(value):
    return set(re.findall(r'[a-z0-9]+', _normal(value))) - _STOP


_NOISE = re.compile(r'\b(?:livraison gratuite|expédition gratuite|free shipping|en promotion|meilleur prix|offre limitée|acheter maintenant)\b.*$', re.I)
_SEPARATOR = re.compile(r'\s+[|–—·]\s+|\s+-\s+')
_SHOP = re.compile(r'^(?:amazon(?:\.[a-z.]+)?|domadoo(?:\.[a-z.]+)?|fnac|cdiscount|aliexpress|ebay(?:\.[a-z.]+)?|boutique officielle|official store)$', re.I)
_GENERIC = re.compile(r'^(?:accueil|home|homepage|welcome|bienvenue|boutique|shop|store|catalogue|catalog|products?|produits?|electronics|electronique|informatique|high tech|domotique|accessoires|amazon(?:\.[a-z.]+)?|domadoo|discord|instagram|ko fi|moes|nabu casa|page introuvable|page not found|access denied|robot check|captcha|connexion|login|sign in|just a moment|promotion exceptionnelle)$')
_BLOCKED = re.compile(r'captcha|robot check|access denied|page introuvable|page not found|just a moment|verify you are human', re.I)
_CATALOGUE_WORDS = set('amazon fr com co uk domadoo livres books dvd musique music jeux video games maison home cuisine kitchen jardin garden bricolage vetements clothing sport loisirs informatique computers electronique electronics accessoires accessories high tech domotique boutique shop store catalogue catalog achat achats vente ligne online shopping'.split())


def clean_title(value, brand='', site=''):
    """Remove identified commercial boilerplate, never blindly split a model."""
    if not isinstance(value, str):
        return ''
    value = html.unescape(re.sub(r'\s+', ' ', value)).strip(' \t\n\r-|–—·:')
    value = re.sub(r'^(?:amazon(?:\.[a-z.]+)?|domadoo)\s*:\s*', '', value, flags=re.I)
    pieces = _SEPARATOR.split(value)
    pieces = [piece for piece in pieces if not _SHOP.fullmatch(piece.strip())
              and not (site and _normal(piece.strip()) == _normal(site.strip()))]
    value = ' – '.join(pieces)
    value = _NOISE.sub('', value).strip(' ,;:-–')
    # Amazon often appends a colon-separated department, not product identity.
    value = re.sub(r'\s*:\s*(?:Amazon\.[a-z.]+)(?:\s*:.*)?$', '', value, flags=re.I)
    if brand and not _tokens(brand) <= _tokens(value):
        value = brand.strip() + ' ' + value
    # Abstain instead of truncating a possibly essential reference at the end.
    return value if 3 <= len(value) <= 120 else ''


def _generic(value, brands=(), *, single_word=True):
    normalized = ' '.join(re.findall(r'[a-z0-9]+', _normal(value)))
    if not normalized or _GENERIC.fullmatch(normalized) or _BLOCKED.search(value):
        return True
    if normalized in {'article', 'lien', 'link', 'nouveau lien', 'sans titre', 'untitled'}:
        return True
    if _tokens(value) <= _CATALOGUE_WORDS:
        return True
    if re.search(r'spend less.*smile more|everything you love|des millions de produits', normalized):
        return True
    if any(_tokens(value) == _tokens(brand) for brand in brands if brand):
        return True
    if re.search(r'^(?:bienvenue|welcome|achats en ligne|achat et vente|online shopping|tous nos produits|toutes les categories)\b', normalized):
        return True
    if all(_GENERIC.fullmatch(' '.join(re.findall(r'[a-z0-9]+', _normal(piece)))) for piece in _SEPARATOR.split(value)):
        return True
    return single_word and len(_tokens(value)) < 2


def _slug_title(url):
    host = (urlsplit(url).hostname or '').lower()
    if any(_host_is(host, domain) for domain in ('discord.gg', 'discord.com', 'instagram.com', 'ko-fi.com')):
        return ''
    parts = [unquote(part) for part in urlsplit(url).path.split('/') if part]
    if not parts:
        return ''
    slug = re.sub(r'\.html?$', '', parts[-1], flags=re.I)
    # PrestaShop/Domadoo catalogue IDs and EANs are not product models.
    slug = re.sub(r'^\d+-', '', slug)
    slug = re.sub(r'-\d{8,14}$', '', slug)
    if not re.search(r'[-_]', slug) or not re.search(r'[a-zA-ZÀ-ÿ]', slug):
        return ''
    title = clean_title(re.sub(r'[-_]+', ' ', slug))
    return title if not _generic(title) else ''


def _host_is(host, domain):
    return host == domain or host.endswith('.' + domain)


def _platform_candidates(url, parser):
    """Small isolated adapters add evidence to the common ranking/comparison."""
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower()
    parts = [unquote(p) for p in parsed.path.split('/') if p]
    if _host_is(host, 'instagram.com') and len(parts) == 1 and re.fullmatch(r'[\w.]{1,30}', parts[0]) and parts[0].lower() not in {'accounts', 'explore', 'reels', 'direct', 'about', 'p', 'reel'}:
        yield ('platform', 'Instagram @' + parts[0], 82)
    if _host_is(host, 'ko-fi.com') and len(parts) == 1:
        value = parser.meta.get('og:title') or ''.join(parser.title)
        match = re.match(r'Buy (.+?) a (?:Coffee|coffee)\b', value)
        if match:
            yield ('platform', 'Offrir un café à ' + match[1].strip(), 85)
    if _host_is(host, 'discord.gg') or (_host_is(host, 'discord.com') and parts[:1] == ['invite']):
        value = clean_title(parser.meta.get('og:title', ''), site='Discord')
        if not _generic(value):
            yield ('platform', 'Discord – ' + value, 82)


_SCORES = {'schema_product': 90, 'schema_content': 82, 'schema_profile': 75,
           'product_heading': 85, 'heading': 76, 'open_graph': 74, 'twitter': 68,
           'html_title': 62, 'url_slug': 50}


def _choose_title(url, parser, current_title, *, fetched=True):
    brands = [parser.meta.get('product:brand', ''), parser.meta.get('og:site_name', '')]
    brands += [''.join(value) for value in parser.brands]
    raw = []
    for script in parser.scripts[:8]:
        try:
            entities = list(islice(_structured(json.loads(script)), 32))
        except (ValueError, RecursionError, TypeError):
            continue
        for source, name, brand, model in entities:
            brands.append(brand)
            title = clean_title(name, brand)
            if title and model and not _tokens(model) <= _tokens(title):
                title = clean_title(title + ' ' + model)
            raw.append((source, title, _SCORES[source]))
    for source, values in (
        ('product_heading', [''.join(p) for p in parser.product_names]),
        ('heading', [''.join(h) for h in parser.headings]),
        ('open_graph', [parser.meta.get('og:title')]),
        ('twitter', [parser.meta.get('twitter:title')]),
        ('html_title', [''.join(parser.title)]),
        ('url_slug', [_slug_title(url)]),
    ):
        for value in values[:8]:
            brand = parser.meta.get('product:brand', '') if source in ('heading', 'product_heading') else ''
            if _generic(clean_title(value), brands):
                continue
            raw.append((source, clean_title(value, brand=brand, site=parser.meta.get('og:site_name', '')), _SCORES[source]))
    platform = list(_platform_candidates(url, parser))
    raw.extend(platform)
    candidates = [(source, title, score) for source, title, score in raw if title and not _generic(title, brands)]
    # Localised, verified platform labels supersede their raw English metadata.
    if platform:
        candidates = platform
    if not candidates:
        return _result(current_title, '', 'unavailable', 'low', 'identity_missing')
    def overlap(a, b):
        ta, tb = _tokens(a), _tokens(b)
        return len(ta & tb) / max(1, min(len(ta), len(tb)))
    ranked = []
    for source, title, score in candidates:
        evidence = {s for s, t, _ in candidates if s != source and overlap(title, t) >= .8}
        ranked.append((score + min(10, len(evidence) * 5), source, title))
    ranked.sort(reverse=True)
    score, source, title = ranked[0]
    # Equally plausible but incompatible identities mean abstention, not guessing.
    for other_score, other_source, other_title in ranked[1:]:
        models = lambda text: {word for word in _tokens(text) if re.search(r'\d', word)}
        incompatible_model = bool(models(title) and models(other_title) and not models(title) <= models(other_title) and not models(other_title) <= models(title))
        if other_source != 'url_slug' and other_score >= 70 and (overlap(title, other_title) < .5 or incompatible_model):
            return _result(current_title, '', 'unavailable', 'low', 'conflicting_metadata')
    confidence = 'high' if score >= 85 else 'medium' if score >= 60 else 'low'
    if not fetched:
        confidence = 'low'
    if current_title:
        before, after = _tokens(current_title), _tokens(title)
        known_brands = set().union(*(_tokens(b) for b in brands if b))
        if before == after or (before <= after and after - before <= known_brands):
            return _result(current_title, source, 'unchanged', confidence, 'already_informative')
        # Preserve all useful current words/references. Only generic labels can be
        # replaced outright; unsupported translations are deliberately avoided.
        if confidence == 'low' or (not _generic(current_title, brands, single_word=False) and not before < after):
            return _result(current_title, source, 'retained', confidence, 'no_proven_gain')
    return _result(title, source, 'ok', confidence, 'more_informative')


def _result(title, source, status, confidence, reason):
    return {'title': title, 'source': source, 'status': status, 'confidence': confidence, 'reason': reason}


def suggest_title(url, *, current_title='', requester=None, resolver=None, url_validator=None):
    """One engine for creation and bulk review; never persists or rewrites URLs.

    Existing titles are preserved unless a candidate demonstrably adds information.
    Confidence is an evidence grade, not a statistical probability.
    """
    current_title = current_title.strip() if isinstance(current_title, str) else ''
    try:
        _target(url)
        response, final_url = _fetch(url, method='GET', max_bytes=MAX_HTML,
                                    requester=requester, resolver=resolver, url_validator=url_validator)
    except InspectionError:
        return _result(current_title, '', 'unavailable', 'low', 'fetch_failed')
    parser = _MetadataParser()
    fetched = 200 <= response.status < 300
    if fetched and not any(x in response.content_type.lower() for x in ('text/html', 'application/xhtml+xml')):
        return _result(current_title, '', 'unavailable', 'low', 'unsupported_content')
    if fetched and any(x in response.content_type.lower() for x in ('text/html', 'application/xhtml+xml')):
        encoding = 'utf-8'
        charset = re.search(r'charset\s*=\s*["\']?([\w-]+)', response.content_type, re.I)
        if charset:
            encoding = charset.group(1)
        try:
            page = response.body.decode(encoding, errors='replace')
        except LookupError:
            page = response.body.decode('utf-8', errors='replace')
        try:
            parser.feed(page)
        except (ValueError, AssertionError):
            return _result(current_title, '', 'unavailable', 'low', 'invalid_html')
        # A challenge/error page may still be returned with HTTP 200.
        if _BLOCKED.search(''.join(parser.title)):
            return _result(current_title, '', 'unavailable', 'low', 'blocked_page')
    return _choose_title(final_url, parser, current_title, fetched=fetched)



def check_destination(url, *, requester=None, resolver=None, url_validator=None):
    """Conservative outcome: valid / broken / unknown.

    Only a GET-confirmed 404/410 is broken; blocked robots, 5xx, TLS failures,
    timeouts and ambiguous redirects are unknown. Never calls a LinKs short URL.
    """
    try:
        response, _ = _fetch(url, method='HEAD', requester=requester, resolver=resolver,
                             url_validator=url_validator)
        if 200 <= response.status < 300:
            return {'status': 'valid', 'http_status': response.status}
        # HEAD is unreliable on some shops; confirm negative statuses via GET.
        response, _ = _fetch(url, method='GET', max_bytes=0, requester=requester, resolver=resolver,
                             url_validator=url_validator)
        if 200 <= response.status < 300:
            return {'status': 'valid', 'http_status': response.status}
        if response.status in (404, 410):
            return {'status': 'broken', 'http_status': response.status}
        return {'status': 'unknown', 'http_status': response.status}
    except InspectionError:
        return {'status': 'unknown', 'http_status': None}
