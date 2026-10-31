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
import zlib
import hashlib
from pathlib import Path
from itertools import islice
from dataclasses import dataclass
from urllib.parse import quote, unquote, urljoin, urlsplit

MAX_URL = 2000
MAX_HTML = 256 * 1024
TIMEOUT = 3
MAX_REDIRECTS = 4
TOTAL_TIMEOUT = 12
USER_AGENT = 'LinKs-URL-Inspector/1.0 (+metadata and availability check)'
ENGINE_ID = 'bounded-metadata-v2'
ENGINE_FINGERPRINT = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]


class InspectionError(Exception):
    """An external URL could not safely or conclusively be inspected."""
    def __init__(self, message, code='invalid_url', stage='url'):
        super().__init__(message)
        self.code, self.stage = code, stage


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str = ''
    body: bytes = b''
    location: str = ''
    truncated: bool = False
    wire_bytes: int = 0
    content_encoding: str = 'identity'


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
        raise InspectionError('Destination locale ou réservée interdite.', 'blocked_destination', 'security')
    try:
        literal = ipaddress.ip_address(host.strip('[]'))
        if not _global_ip(literal):
            raise InspectionError('Adresse IP non publique interdite.', 'blocked_destination', 'security')
    except ValueError:
        if '.' not in host or any(not part for part in host.split('.')):
            raise InspectionError('Nom de domaine public requis.')
    path = quote(parsed.path or '/', safe="/%:@!$&'()*+,;=-._~")
    if parsed.query:
        path += '?' + quote(parsed.query, safe="%/?@:!$&'()*+,;=-._~")
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
            raise InspectionError('Résolution DNS non publique ou ambiguë.', 'blocked_destination', 'security')
        return addresses[0]
    except (OSError, ValueError) as exc:
        raise InspectionError('Résolution DNS impossible ou non fiable.', 'dns_error', 'dns') from exc


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
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'close',
        })
        response = connection.getresponse()
        body = b''
        truncated, wire_bytes = False, 0
        encoding = response.getheader('Content-Encoding', 'identity').strip().lower() or 'identity'
        if method == 'GET' and max_bytes and response.status not in (301, 302, 303, 307, 308):
            if encoding not in ('identity', 'gzip', 'deflate'):
                raise InspectionError('Encodage non pris en charge.', 'unsupported_encoding', 'http')
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == 'gzip' else zlib.MAX_WBITS) if encoding != 'identity' else None
            # Bound both transferred and decompressed bytes. The page may be larger;
            # complete metadata in this prefix is still useful. Never fetch its tail.
            while len(body) <= max_bytes and wire_bytes <= max_bytes:
                # read1 avoids waiting for the entire body; bound every socket read.
                sock = connection.sock or getattr(getattr(response.fp, 'raw', None), '_sock', None)
                if sock:
                    sock.settimeout(min(TIMEOUT, _remaining(deadline)))
                _remaining(deadline)
                block = response.read1(min(16384, max_bytes + 1 - wire_bytes))
                if not block:
                    if decoder and not decoder.eof:
                        raise InspectionError('Réponse compressée incomplète.', 'invalid_compression', 'http')
                    break
                wire_bytes += len(block)
                try:
                    body += decoder.decompress(block, max_bytes + 1 - len(body)) if decoder else block
                except zlib.error as exc:
                    raise InspectionError('Réponse compressée invalide.', 'invalid_compression', 'http') from exc
                if len(body) > max_bytes or wire_bytes > max_bytes:
                    truncated = True
                    body = body[:max_bytes]
                    break
        return Response(response.status, response.getheader('Content-Type', ''), body,
                        response.getheader('Location', ''), truncated, wire_bytes, encoding)
    except InspectionError as exc:
        exc.http_status = response.status if response else None
        raise
    finally:
        watchdog.cancel()
        if response is not None:
            response.close()
        connection.close()


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise InspectionError('Délai global de récupération dépassé.', 'deadline_exceeded', 'network')
    return remaining


# DNS has no portable socket timeout. Limit outstanding resolver workers as well
# as caller wait time, so stalled DNS cannot accumulate unbounded threads.
_DNS_SLOTS = threading.BoundedSemaphore(8)


def _resolve_before_deadline(target, resolver, deadline):
    if not _DNS_SLOTS.acquire(blocking=False):
        raise InspectionError('Résolution DNS occupée.', 'dns_busy', 'dns')
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
        raise InspectionError('Délai DNS dépassé.', 'dns_timeout', 'dns') from exc
    if not ok:
        raise value
    return value


def _fetch(url, *, method, max_bytes=0, requester=None, resolver=None, url_validator=None, diagnostics=None):
    requester = requester or _request_once
    resolver = resolver or socket.getaddrinfo
    seen = set()
    deadline = time.monotonic() + TOTAL_TIMEOUT
    trace = diagnostics if diagnostics is not None else {}
    for redirect_count in range(MAX_REDIRECTS + 1):
        trace['redirects'] = redirect_count
        _remaining(deadline)
        try:
            target = _target(url)
        except InspectionError as exc:
            if redirect_count and exc.stage == 'url':
                exc.code, exc.stage = 'redirect_invalid', 'redirect'
            raise
        if url_validator is not None and not url_validator(target.url):
            raise InspectionError('Destination exclue de la vérification.', 'blocked_destination', 'security')
        if target.url in seen:
            raise InspectionError('Boucle de redirection.', 'redirect_loop', 'redirect')
        seen.add(target.url)
        try:
            ip = _resolve_before_deadline(target, resolver, deadline)
            trace['dns'] = 'public'
            result = (requester(target, ip, method, max_bytes, deadline=deadline)
                      if requester is _request_once else requester(target, ip, method, max_bytes))
        except InspectionError as exc:
            exc.fallback_url = target.url
            raise
        except (OSError, TimeoutError, ssl.SSLError, http.client.HTTPException, UnicodeError) as exc:
            code = 'tls_error' if isinstance(exc, ssl.SSLError) else 'network_timeout' if isinstance(exc, TimeoutError) else 'http_protocol_error' if isinstance(exc, http.client.HTTPException) else 'url_encoding_error' if isinstance(exc, UnicodeError) else 'network_error'
            error = InspectionError('La destination ne répond pas de manière fiable.', code, 'network')
            error.fallback_url = target.url
            raise error from exc
        if not isinstance(result, Response):
            raise InspectionError('Réponse de vérification invalide.', 'http_protocol_error', 'http')
        _remaining(deadline)
        if len(result.body) > max_bytes and max_bytes:
            result = Response(result.status, result.content_type, result.body[:max_bytes], result.location, True, min(result.wire_bytes or len(result.body), max_bytes + 1), result.content_encoding)
        trace.update(http_status=result.status, bytes_read=len(result.body), wire_bytes=result.wire_bytes,
                     truncated=result.truncated, content_encoding=result.content_encoding)
        trace.setdefault('hops', []).append({'http_status': result.status})
        if result.status in (301, 302, 303, 307, 308):
            if not result.location:
                raise InspectionError('Redirection sans destination.', 'redirect_missing', 'redirect')
            try:
                url = urljoin(url, result.location)
            except ValueError as exc:
                raise InspectionError('Destination de redirection invalide.', 'redirect_invalid', 'redirect') from exc
            continue
        return result, target.url
    raise InspectionError('Trop de redirections.', 'redirect_limit', 'redirect')


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

    def finish(self):
        # A bounded prefix may end inside a heading, title or JSON-LD script.
        # Only closed elements may identify a destination.
        for _, capture, _ in self._captures:
            capture.clear()
        self._captures.clear()

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


def _truncated_title(value):
    # An incomplete connector/ellipsis is a warning, never permission to guess
    # missing specifications. A symbol inside a model (C++, A&B) is not truncated.
    return bool(re.search(r'(?:\s&|\s(?:et|avec|pour)|\.{3}|…)$', value.strip(), re.I))


def _compact_product(value, url):
    """Keep the existing attested labels, including every optional specification."""
    if _truncated_title(value) or not _host_is((urlsplit(url).hostname or '').lower(), 'domadoo.fr'):
        return value
    words = ' '.join(re.findall(r'[a-z0-9]+', _normal(value)))
    if re.fullmatch(r'(?:nabu casa )?(?:box domotique )?home assistant green', words):
        return 'Home Assistant Green'
    match = re.fullmatch(r'moes capteur (?:de )?co (?:monoxyde de carbone )?zigbee(?P<tuya> tuya)?(?P<model> zc hm)?', words)
    if match:
        return 'Capteur CO Zigbee MOES' + (' Tuya' if match['tuya'] else '') + (' ZC-HM' if match['model'] else '')
    return value


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


def _choose_title(url, parser, current_title, *, fetched=True, diagnostics=None):
    trace = diagnostics if diagnostics is not None else {}
    brands = [parser.meta.get('product:brand', ''), parser.meta.get('og:site_name', '')]
    brands += [''.join(value) for value in parser.brands]
    raw = []
    for script in parser.scripts[:8]:
        try:
            entities = list(islice(_structured(json.loads(script)), 32))
        except (ValueError, RecursionError, TypeError):
            trace['invalid_jsonld'] = trace.get('invalid_jsonld', 0) + 1
            continue
        for source, name, brand, model in entities:
            brands.append(brand)
            title = clean_title(name, brand)
            if title and model and not _tokens(model) <= _tokens(title):
                title = clean_title(title + ' ' + model)
            raw.append((source, _compact_product(title, url), _SCORES[source]))
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
            cleaned = clean_title(value, site=parser.meta.get('og:site_name', ''))
            if isinstance(value, str) and value.strip() and not cleaned:
                trace['rejected_generic'] = trace.get('rejected_generic', 0) + 1
            if cleaned and not _generic(cleaned, brands):
                cleaned = clean_title(cleaned, brand=brand)
            score = 65 if source == 'url_slug' and len(_tokens(cleaned)) >= 3 else _SCORES[source]
            raw.append((source, _compact_product(cleaned, url), score))
    platform = list(_platform_candidates(url, parser)) if fetched else []
    raw.extend(platform)
    candidates = [(source, title, score) for source, title, score in raw if title and not _generic(title, brands) and not _truncated_title(title)]
    trace['rejected_truncated'] = sum(bool(title) and _truncated_title(title) for _, title, _ in raw)
    trace.update(metadata=len(parser.meta), headings=sum(bool(''.join(h)) for h in parser.headings),
                 jsonld=len(parser.scripts), candidates=len(candidates),
                 rejected_generic=trace.get('rejected_generic', 0) + sum(bool(title) and _generic(title, brands) for _, title, _ in raw))
    # Localised, verified platform labels supersede their raw English metadata.
    if platform:
        candidates = [candidate for candidate in candidates if candidate[0]=='platform']
    if not candidates:
        reason = 'truncated_metadata' if trace['rejected_truncated'] else 'generic_metadata' if trace['rejected_generic'] else 'invalid_jsonld' if trace.get('invalid_jsonld') else 'metadata_missing'
        return _result(current_title, '', 'unavailable', 'low', reason)
    def overlap(a, b):
        ta, tb = _tokens(a), _tokens(b)
        return len(ta & tb) / max(1, min(len(ta), len(tb)))
    ranked = []
    for source, title, score in candidates:
        evidence = {s for s, t, _ in candidates if s != source and overlap(title, t) >= .8}
        ranked.append((score + min(10, len(evidence) * 5), source, title))
    ranked.sort(reverse=True)
    score, source, title = ranked[0]
    trace.update(selected_source=source, score=score)
    # Equally plausible but incompatible identities mean abstention, not guessing.
    for other_score, other_source, other_title in ranked[1:]:
        models = lambda text: {word for word in _tokens(text) if re.search(r'\d', word)}
        incompatible_model = bool(models(title) and models(other_title) and not models(title) <= models(other_title) and not models(other_title) <= models(title))
        if other_source != 'url_slug' and other_score >= 70 and (overlap(title, other_title) < .5 or incompatible_model):
            return _result(current_title, '', 'unavailable', 'low', 'conflicting_metadata')
    confidence = 'high' if score >= 85 else 'medium' if score >= 60 else 'low'
    if not fetched and source != 'url_slug':
        confidence = 'low'
    if current_title:
        host = (urlsplit(url).hostname or '').lower()
        if any(_host_is(host, domain) for domain in ('discord.gg', 'discord.com', 'instagram.com')):
            return _result(current_title, source, 'retained', confidence, 'platform_title_preserved')
        before, after = _tokens(current_title), _tokens(title)
        known_brands = set().union(*(_tokens(b) for b in brands if b))
        if before == after or (before <= after and after - before <= known_brands):
            return _result(current_title, source, 'unchanged', confidence, 'already_informative')
        # Preserve all useful current words/references. Only generic labels can be
        # replaced outright; unsupported translations are deliberately avoided.
        if confidence == 'low' or (not _generic(current_title, brands, single_word=False) and not before < after):
            return _result(current_title, source, 'retained', confidence, 'score_too_low' if confidence == 'low' else 'no_proven_gain')
    return _result(title, source, 'ok', confidence, 'more_informative')


def _result(title, source, status, confidence, reason):
    return {'title': title, 'source': source, 'status': status, 'confidence': confidence, 'reason': reason}


# Deliberately small, contextual rules, not a general spelling/grammar checker.
# Protect opaque identifiers, quoted names and explicit model/reference tails.
_EDITORIAL_PROTECTED = re.compile(
    r'"[^"\n]*"|«[^»\n]*»|`[^`\n]*`|'
    r'\b(?:réf(?:érence)?\.?|ref(?:erence)?\.?|modèle|model)\s*[:=]?\s+[^,;\n]+|'
    r'\S*[\d_/@#=+\\]\S*|\S*\w[-.:]\w\S*', re.I)
_EDITORIAL_BRANDS = ('Home Assistant Green', 'Home Assistant',
                     'Zigbee', 'Discord', 'Instagram', 'MOES', 'SONOFF',
                     'Aqara', 'Tuya', 'Bluetooth')
_EDITORIAL_BRAND_PATTERN = re.compile(
    r'(?<![\w@./+#:-])(?ai:' + '|'.join(map(re.escape, _EDITORIAL_BRANDS)) + r')(?![\w@./+#:-])')
_EDITORIAL_CANONICAL = {name.casefold(): name for name in _EDITORIAL_BRANDS}


def _editorial_title(current):
    """Only attested local corrections; never truncate or infer technical facts."""
    value, rules = current, []

    # Reformat a model followed by a descriptive comma list without cutting any
    # specification. A complete model token is required; names/quoted text stay intact.
    model = r'\b(?=\w*[A-Za-z])(?=\w*\d)\w[\w.+-]*\b'
    if not re.search(r'["«»`]|\b(?:réf(?:érence)?|ref(?:erence)?|modèle|model)\b', value, re.I):
        identity, comma, description = value.partition(', ')
        if comma and re.search(model, identity) and re.match(r'^[a-zà-ÿ]{3,}\b', description):
            # FRA is the redundant catalogue label in the requested French
            # AZERTY presentation. Other national/layout variants are preserved.
            if re.match(r'^clavier\b', description, re.I):
                simplified = re.sub(r',\s*FRA\s+AZERTY\b', ' AZERTY', description)
                if simplified != description:rules.append('keyboard_layout_label')
                description = simplified
            value = identity + ' – ' + description[0].upper() + description[1:]
            rules.append('product_list_punctuation')
        if re.search(model, value) and re.search(r'\s&$', value):
            value = re.sub(r'\s+&$', '', value)
            rules.append('dangling_ampersand')

    def apply(pattern, replacement, rule):
        nonlocal value
        protected = [match.span() for match in _EDITORIAL_PROTECTED.finditer(value)
                     if match.group().casefold() not in {'paye-moi', 'paie-moi'}]
        def replace(match):
            if any(start < match.end() and match.start() < end for start, end in protected):
                return match.group()
            return replacement(match)
        updated = pattern.sub(replace, value)
        if updated != value:
            rules.append(rule)
            value = updated

    # Exact French phrase: preserve either accepted spelling, paye or paie.
    apply(re.compile(r'^(Paye|paye|Paie|paie)(?: +|-)[Mm]oi +un +caf[eé](?=\s*[!?…]?\s*$)'),
          lambda m: m[1].capitalize() + '-moi un café', 'coffee_phrase')
    apply(re.compile(r'\b((?:[Cc]apteurs?|[Ss]ondes?|[Mm]esures?) de )temperature(s?)\b'),
          lambda m: m[1] + 'température' + m[2], 'temperature_accent')
    apply(re.compile(r"\b((?:[Cc]apteurs?|[Ss]ondes?|[Mm]esures?|et) d['’])humidite\b"),
          lambda m: m[1] + 'humidité', 'humidity_accent')
    apply(re.compile(r'\b([Dd])etecteur(s? de )'),
          lambda m: m[1] + 'étecteur' + m[2], 'detector_accent')
    apply(_EDITORIAL_BRAND_PATTERN,
          lambda m: _EDITORIAL_CANONICAL[m.group().casefold()], 'brand_case')
    # French terminal punctuation, only after recognisable French prose. Do not
    # rewrite decimals, ratios, model separators, apostrophes or arbitrary names.
    if re.match(r"^(?:Paye-moi un café|Paie-moi un café|[Cc]apteurs? de |[Ss]ondes? de |[Dd]étecteurs? de )", value):
        apply(re.compile(r'(?<=[a-zà-ÿ])([!?])$'),
              lambda m: '\u00a0' + m[1], 'french_punctuation')
    # The existing manual field accepts 160 characters; no information is cut.
    return (value, rules) if len(value) <= 160 else (current, [])


def _relevant_platform_label(url, current):
    parsed = urlsplit(url)
    parts = [unquote(p) for p in parsed.path.split('/') if p]
    if not _host_is((parsed.hostname or '').lower(), 'instagram.com') or len(parts) != 1:
        return False
    if not re.fullmatch(r'[\w.]{1,30}', parts[0]) or parts[0].lower() in {'accounts','explore','reels','direct','about','p','reel'}:
        return False
    return bool(re.fullmatch(r'Instagram(?:\s+[–—-]?\s*@' + re.escape(parts[0]) + r')?', current, re.I))


def suggest_title(url, *, current_title='', requester=None, resolver=None, url_validator=None):
    """One engine for creation and bulk review; never persists or rewrites URLs.

    Existing titles change only for demonstrated information gains or safe local corrections.
    Confidence is an evidence grade, not a statistical probability.
    """
    current_title = current_title.strip() if isinstance(current_title, str) else ''
    trace = {'fetch': {'outcome': 'not_started'}, 'extraction': {'outcome': 'not_attempted'}}
    def finish(result):
        # A reliable destination improvement takes precedence. Otherwise improve
        # only the current text, independently of network/extraction availability.
        if current_title and result['status'] != 'ok':
            corrected, rules = _editorial_title(current_title)
            if corrected != current_title:
                trace['destination_decision'] = {key: result[key] for key in ('status', 'reason', 'source', 'confidence')}
                trace['editorial'] = {'rules': rules}
                partial = _truncated_title(current_title)
                result = _result(corrected, 'editorial', 'ok', 'medium' if partial else 'high', 'editorial_truncated' if partial else 'editorial_correction')
            elif _truncated_title(current_title) and result['reason'] not in {'blocked_destination','invalid_url'} and not result['reason'].startswith('redirect_'):
                trace['destination_decision'] = {key: result[key] for key in ('status', 'reason', 'source', 'confidence')}
                result = _result(current_title, 'current_title', 'retained', 'low', 'current_title_truncated')
            elif result['reason'] not in {'blocked_destination','invalid_url','conflicting_metadata'} and not result['reason'].startswith('redirect_'):
                if _relevant_platform_label(url, current_title):
                    trace['destination_decision'] = {key: result[key] for key in ('status', 'reason', 'source', 'confidence')}
                    result = _result(current_title, 'current_title', 'unchanged', 'medium', 'platform_label_relevant')
                elif result['status']=='unavailable' and result['reason']=='generic_metadata' and not _generic(current_title):
                    result.update(status='retained', source='current_title')
        elif current_title and result['status']=='ok':
            # The evidence/source remains the destination (or its descriptive URL),
            # even when presentation is improved by the same local rules.
            corrected, rules = _editorial_title(result['title'])
            if corrected != result['title']:
                result['title'] = corrected
                trace['editorial'] = {'rules': rules}
        result['engine'] = {'id': ENGINE_ID, 'fingerprint': ENGINE_FINGERPRINT}
        trace['decision'] = {key: result[key] for key in ('status', 'reason', 'source', 'confidence')}
        result['diagnostics'] = trace
        return result
    def fallback(target_url, reason):
        result = _choose_title(target_url, _MetadataParser(), current_title, fetched=False,
                               diagnostics=trace['extraction'])
        trace['extraction']['outcome'] = 'url_only'
        if result['source'] == 'url_slug':
            if result['status'] == 'unchanged':
                result.update(status='retained', reason='url_matches_current')
            elif result['status'] == 'ok':
                result['reason'] = 'url_fallback'
        else:
            result['reason'] = reason
        return finish(result)
    try:
        _target(url)
        response, final_url = _fetch(url, method='GET', max_bytes=MAX_HTML,
                                    requester=requester, resolver=resolver, url_validator=url_validator,
                                    diagnostics=trace['fetch'])
    except InspectionError as exc:
        trace['fetch'].update(outcome='error', stage=exc.stage, code=exc.code)
        if getattr(exc, 'http_status', None) is not None:
            trace['fetch']['http_status'] = exc.http_status
        # Network/HTTP failure does not erase information present in a public URL.
        # Security or redirect failures never turn into apparent successful analysis.
        if exc.code in {'dns_error', 'dns_timeout', 'dns_busy', 'network_timeout', 'network_error',
                        'tls_error', 'deadline_exceeded', 'unsupported_encoding', 'invalid_compression'}:
            return fallback(getattr(exc, 'fallback_url', url), exc.code)
        return finish(_result(current_title, '', 'unavailable', 'low', exc.code))
    parser = _MetadataParser()
    fetched = 200 <= response.status < 300
    trace['fetch'].update(outcome='partial' if response.truncated else 'ok',
                          code='body_limit' if response.truncated else 'ok')
    if not fetched:
        reason = 'http_' + str(response.status)
        trace['fetch'].update(outcome='http_error', code=reason)
        return fallback(final_url, reason)
    if fetched and not any(x in response.content_type.lower() for x in ('text/html', 'application/xhtml+xml')):
        trace['extraction'].update(outcome='skipped', code='unsupported_content')
        return finish(_result(current_title, '', 'unavailable', 'low', 'unsupported_content'))
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
            parser.finish()
        except (ValueError, AssertionError):
            trace['extraction']['code'] = 'invalid_html'
            return fallback(final_url, 'invalid_html')
        # A challenge/error page may still be returned with HTTP 200.
        if _BLOCKED.search(''.join(parser.title)):
            trace['extraction']['code'] = 'blocked_page'
            return fallback(final_url, 'blocked_page')
    trace['extraction']['outcome'] = 'parsed'
    result = _choose_title(final_url, parser, current_title, fetched=fetched, diagnostics=trace['extraction'])
    if result['source'] == 'url_slug':
        if result['status'] == 'ok':
            result['reason'] = 'url_fallback'
        elif result['status'] == 'unchanged':
            result.update(status='retained', reason='url_matches_current')
    return finish(result)



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
