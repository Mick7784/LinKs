"""Reproduce V1.331 failures through the real bounded transport, offline."""
import gzip
import io
import json
from pathlib import Path
import socket
import ssl
import unittest
from unittest.mock import patch
import zlib

import url_inspection as ui
from url_inspection_test import public_resolver, reply

FIXTURES = Path(__file__).parent / 'fixtures/titles'
GREEN = 'https://www.domadoo.fr/fr/produits-compatibles-home-assistant/7046-nabu-casa-box-domotique-home-assistant-green-0860011789703.html?domid=117'
MOES = 'https://www.domadoo.fr/fr/peripheriques/6933-moes-capteur-de-co-monoxyde-de-carbone-zigbee-tuya-zc-hm.html'


class TransportFixture:
    """A socket-free HTTP response; all production read/parse/decision code runs."""
    def __init__(self, body, encoding='identity', declared=True):
        self.body = gzip.compress(body) if encoding == 'gzip' else zlib.compress(body) if encoding == 'deflate' else body
        self.encoding, self.declared = encoding, declared
        self.read_bytes = 0
        self.closed = False
        self.request_headers = None

    def connection(self, *args, **kwargs):
        fixture = self
        class Response:
            status = 200
            fp = None
            stream = io.BytesIO(fixture.body)
            def getheader(self, name, default=''):
                return {'Content-Type':'text/html; charset=utf-8', 'Content-Encoding':fixture.encoding,
                        'Content-Length':str(len(fixture.body)) if fixture.declared else ''}.get(name, default)
            def read1(self, size):
                data = self.stream.read(size)
                fixture.read_bytes += len(data)
                return data
            def close(self):
                fixture.closed = True
        class Connection:
            sock = None
            def request(self, method, path, headers):
                fixture.request_headers = headers
            def getresponse(self):
                return Response()
            def close(self):
                fixture.closed = True
        return Connection()

    def suggest(self, url, current=''):
        with patch.object(ui, '_PinnedHTTPS', self.connection):
            return ui.suggest_title(url, current_title=current, resolver=public_resolver)


class TitleFetchRegressionTests(unittest.TestCase):
    def test_actual_metadata_survives_oversize_identity_chunked_gzip_and_deflate(self):
        cases = [('domadoo-green.html', GREEN, 'Home Assistant Green', 'Home Assistant Green', 'unchanged'),
                 ('domadoo-moes.html', MOES, 'Capteur CO MOES', 'Capteur CO Zigbee MOES Tuya ZC-HM', 'ok'),
                 ('kofi.html', 'https://ko-fi.com/domotik_studio', 'Paye-moi un café', 'Paye-moi un café', 'retained')]
        for name, url, current, expected, status in cases:
            # Only the relevant, public metadata is stored; padding reproduces page size.
            body = (FIXTURES/name).read_bytes() + b' ' * (ui.MAX_HTML * 2)
            for encoding, declared in [('identity', True), ('identity', False), ('gzip', True), ('deflate', False)]:
                with self.subTest(page=name, encoding=encoding, declared=declared):
                    fixture = TransportFixture(body, encoding, declared)
                    result = fixture.suggest(url, current)
                    self.assertEqual((result['title'], result['status'], result['confidence']), (expected, status, 'high'))
                    self.assertEqual(result['diagnostics']['fetch']['bytes_read'], ui.MAX_HTML)
                    self.assertTrue(result['diagnostics']['fetch']['truncated'])
                    self.assertLessEqual(fixture.read_bytes, ui.MAX_HTML + 1)
                    self.assertTrue(fixture.closed)

    def test_unclosed_metadata_at_limit_is_never_a_product(self):
        for incomplete in [b'<h1>Capteur CO Zigbee MOES', b'<title>Capteur CO Zigbee MOES',
                           b'<script type="application/ld+json">{"@type":"Product","name":"Capteur CO MOES"',
                           b'<meta property="og:title" content="Capteur CO MOES']:
            body = b' ' * (ui.MAX_HTML - len(incomplete)) + incomplete + b' more' * 100
            result = TransportFixture(body).suggest('https://shop.example/item', 'Titre manuel')
            self.assertEqual((result['title'], result['status']), ('Titre manuel', 'unavailable'))
            self.assertEqual(result['reason'], 'metadata_missing')

    def test_gzip_expansion_is_bounded(self):
        body = b'<h1>Capteur CO MOES</h1>' + b' ' * (5 * 1024 * 1024)
        fixture = TransportFixture(body, 'gzip')
        result = fixture.suggest('https://shop.example/item')
        self.assertEqual(result['title'], 'Capteur CO MOES')
        self.assertEqual(result['diagnostics']['fetch']['bytes_read'], ui.MAX_HTML)
        self.assertLessEqual(fixture.read_bytes, ui.MAX_HTML + 1)

    def test_compression_failures_have_specific_reasons(self):
        for encoding, body, expected in [('br', b'abc', 'unsupported_encoding'), ('gzip', b'not gzip', 'invalid_compression')]:
            fixture = TransportFixture(body)
            fixture.encoding = encoding
            result = fixture.suggest('https://shop.example/item', 'Titre manuel')
            self.assertEqual((result['status'], result['reason']), ('unavailable', expected))
            self.assertEqual(result['diagnostics']['fetch']['http_status'], 200)

    def test_network_failure_can_use_verified_url_words_without_fabricating_features(self):
        def offline(*args):
            raise OSError('secret internal exception')
        for url, expected in [(GREEN, 'Home Assistant Green'), (MOES, 'Capteur CO Zigbee MOES Tuya ZC-HM')]:
            result = ui.suggest_title(url, current_title='NABU CASA' if url == GREEN else 'Capteur CO MOES',
                                      requester=offline, resolver=public_resolver)
            self.assertEqual((result['title'], result['status'], result['confidence']), (expected, 'ok', 'medium'))
            self.assertEqual(result['reason'], 'url_fallback')
            self.assertEqual(result['diagnostics']['fetch']['code'], 'network_error')
        result = ui.suggest_title('https://www.domadoo.fr/fr/1234-moes-capteur-co.html',
                                  requester=offline, resolver=public_resolver)
        self.assertNotIn('zigbee', result['title'].lower())

    def test_matching_slug_does_not_claim_successful_metadata_extraction(self):
        result = ui.suggest_title(GREEN, current_title='Home Assistant Green',
                                  requester=lambda *args: reply(403), resolver=public_resolver)
        self.assertEqual((result['title'], result['status'], result['reason']),
                         ('Home Assistant Green', 'retained', 'url_matches_current'))
        self.assertEqual(result['diagnostics']['fetch']['code'], 'http_403')

    def test_short_link_fallback_uses_last_resolved_url(self):
        def request(target, *args):
            if target.host == 'short.example':
                return reply(302, location=MOES)
            raise TimeoutError()
        result = ui.suggest_title('https://short.example/a', current_title='MOES', requester=request, resolver=public_resolver)
        self.assertEqual(result['title'], 'Capteur CO Zigbee MOES Tuya ZC-HM')
        self.assertEqual(result['diagnostics']['fetch']['redirects'], 1)
        self.assertEqual(result['diagnostics']['fetch']['hops'], [{'http_status':302}])
        self.assertEqual(result['diagnostics']['fetch']['code'], 'network_timeout')

    def test_network_http_redirect_extraction_and_score_are_distinct(self):
        for error, code in [(TimeoutError(), 'network_timeout'), (OSError(), 'network_error'), (ssl.SSLError(), 'tls_error')]:
            with self.subTest(code=code):
                def request(*args):
                    raise error
                result = ui.suggest_title('https://shop.example/item', current_title='Titre manuel', requester=request, resolver=public_resolver)
                self.assertEqual((result['status'], result['reason']), ('unavailable', code))
        def missing_dns(*args, **kwargs):
            raise socket.gaierror()
        result = ui.suggest_title('https://shop.example/item', resolver=missing_dns)
        self.assertEqual(result['reason'], 'dns_error')
        for status in [403, 404, 429, 503]:
            result = ui.suggest_title('https://amazon.fr/dp/B012345678', current_title='Produit Amazon existant',
                requester=lambda *args: reply(status), resolver=public_resolver)
            self.assertEqual((result['title'], result['reason']), ('Produit Amazon existant', f'http_{status}'))
        for response, reason in [(reply(302), 'redirect_missing'), (reply(302, location='/item'), 'redirect_loop'),
                                 (reply(html=''), 'metadata_missing'), (reply(html='<title>Amazon</title>'), 'generic_metadata'),
                                 (reply(html='<script type="application/ld+json">{broken}</script>'), 'invalid_jsonld')]:
            result = ui.suggest_title('https://shop.example/item', requester=lambda *args: response, resolver=public_resolver)
            self.assertEqual(result['reason'], reason)
        result = ui.suggest_title('https://shop.example/camera-reolink', current_title='Reolink',
                                 requester=lambda *args: reply(html=''), resolver=public_resolver)
        self.assertEqual(result['reason'], 'score_too_low')

    def test_private_redirect_cannot_turn_into_slug_success(self):
        result = ui.suggest_title(GREEN, current_title='NABU CASA',
            requester=lambda *args: reply(302, location='http://169.254.169.254/private'), resolver=public_resolver)
        self.assertEqual((result['title'], result['status'], result['reason']), ('NABU CASA', 'unavailable', 'blocked_destination'))

    def test_platform_label_is_distinct_from_unverified_profile_identity(self):
        for url, title in [('https://instagram.com/domotik_studio', 'Instagram'), ('https://discord.gg/abcdef', 'Ma communauté')]:
            result = ui.suggest_title(url, current_title=title, requester=lambda *args: reply(html='<meta property="og:title" content="Domotik Studio">'), resolver=public_resolver)
            self.assertEqual(result['title'], title)
            self.assertEqual(result['status'], 'unchanged' if title=='Instagram' else 'retained')
            result = ui.suggest_title(url, current_title=title, requester=lambda *args: reply(429), resolver=public_resolver)
            if title=='Instagram':
                self.assertEqual((result['title'], result['status'], result['reason']), (title, 'unchanged', 'platform_label_relevant'))
                self.assertEqual(result['diagnostics']['fetch']['code'], 'http_429')
                self.assertEqual(result['diagnostics']['destination_decision']['status'], 'unavailable')
            else:self.assertEqual((result['title'], result['status'], result['reason']), (title, 'unavailable', 'http_429'))

    def test_diagnostics_do_not_expose_url_parameters_page_data_ip_or_exception(self):
        def request(*args):
            raise OSError('secretexception')
        result = ui.suggest_title('https://shop.example/item?token=secretquery#secretfragment', current_title='Titre privé',
                                 requester=request, resolver=public_resolver)
        diagnostic = json.dumps(result['diagnostics'])
        for forbidden in ['secret', 'Titre privé', 'shop.example', '93.184.216.34', '?token']:
            self.assertNotIn(forbidden, diagnostic)
        self.assertLess(len(diagnostic), 1500)


if __name__ == '__main__':
    unittest.main()
