"""Offline title quality and transport regressions. All product data is synthetic."""
import json
from pathlib import Path
import socket
import time
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import url_inspection as ui
from url_inspection_test import public_resolver, reply


class TitleQualityTests(unittest.TestCase):
    def test_fixture_corpus(self):
        fixtures = json.loads((Path(__file__).parent / 'fixtures/title_metadata.json').read_text(encoding='utf-8'))
        for fixture in fixtures:
            with self.subTest(case=fixture['case']):
                result = ui.suggest_title(fixture['url'], current_title=fixture['current'],
                    requester=lambda *args: reply(fixture.get('http', 200), html=fixture['html']),
                    resolver=public_resolver)
                self.assertEqual(result['title'], fixture['expected'])
                self.assertEqual(result['status'], fixture['status'])
                self.assertEqual(result['confidence'], fixture['confidence'])

    def test_short_amazon_url_uses_resolved_product_without_mutating_input(self):
        url = 'https://amzn.to/example?tag=original-21'
        calls = []
        def request(target, ip, method, limit):
            calls.append(target.url)
            if len(calls) == 1:
                return reply(302, location='https://www.amazon.fr/dp/B012345678?tag=original-21')
            return reply(html='<span id="productTitle">Capteur CO MOES</span>')
        result = ui.suggest_title(url, current_title='Amazon', requester=request, resolver=public_resolver)
        self.assertEqual(result['title'], 'Capteur CO MOES')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(calls, [url, 'https://www.amazon.fr/dp/B012345678?tag=original-21'])
        self.assertNotIn('url', result)

    def test_inaccessible_short_amazon_url_keeps_current_title(self):
        result = ui.suggest_title('https://amzn.to/abcdef', current_title='Home Assistant Green',
            requester=lambda *args: reply(403), resolver=public_resolver)
        self.assertEqual((result['title'], result['status']), ('Home Assistant Green', 'unavailable'))

    def test_identity_cannot_be_guessed_from_instagram_reserved_path_or_fake_host(self):
        for url in ['https://instagram.com/accounts/', 'https://instagram.com/p/ABC/',
                    'https://instagram.com.evil.example/mickael/']:
            with self.subTest(url=url):
                result = ui.suggest_title(url, requester=lambda *args: reply(html='<title>Instagram</title>'), resolver=public_resolver)
                self.assertEqual(result['status'], 'unavailable')

    def test_long_title_does_not_silently_drop_model(self):
        title = 'Capteur ' + 'caractéristique ' * 12 + 'MODEL-VERIFIED-42'
        self.assertEqual(ui.clean_title(title), '')

    def test_existing_single_word_model_is_not_a_generic_brand(self):
        result = ui.suggest_title('https://shop.example/item', current_title='DXP4800',
            requester=lambda *args: reply(html='<h1>UGREEN DXP6800 Pro</h1>'), resolver=public_resolver)
        self.assertEqual((result['title'], result['status']), ('DXP4800', 'retained'))

    def test_product_heading_keeps_brand_from_product_metadata(self):
        result = ui.suggest_title('https://www.domadoo.fr/item', current_title='MOES',
            requester=lambda *args: reply(html='<meta property="product:brand" content="MOES"><h1>Capteur CO</h1>'), resolver=public_resolver)
        self.assertEqual((result['title'], result['status']), ('MOES Capteur CO', 'ok'))

    def test_amazon_catalogue_variants_are_not_products(self):
        for title in ['Amazon.fr : Livres, DVD, musique, jeux vidéo', 'Amazon.com. Spend less. Smile more.', 'Maison, cuisine et jardin']:
            with self.subTest(title=title):
                result = ui.suggest_title('https://www.amazon.fr/dp/B012345678', current_title='MOES',
                    requester=lambda *args: reply(html='<title>'+title+'</title>'), resolver=public_resolver)
                self.assertEqual((result['title'], result['status']), ('MOES', 'unavailable'))

    def test_malformed_redirect_is_nonfatal(self):
        result = ui.suggest_title('https://shop.example/item', current_title='Mon produit',
            requester=lambda *args: reply(302, location='https://[invalid'), resolver=public_resolver)
        self.assertEqual((result['title'], result['status']), ('Mon produit', 'unavailable'))

    def test_unsafe_redirect_never_falls_back_to_unverified_slug(self):
        calls = []
        def request(*args):
            calls.append(args)
            return reply(302, location='http://169.254.169.254/latest/meta-data')
        result = ui.suggest_title('https://shop.example/home-assistant-green', current_title='Mon produit', requester=request, resolver=public_resolver)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['title'], 'Mon produit')
        self.assertEqual(len(calls), 1)

    def test_validator_applies_to_redirects_before_request(self):
        calls = []
        def request(target, *args):
            calls.append(target.url)
            return reply(302, location='https://links.example/tracked')
        result = ui.suggest_title('https://shop.example/item', requester=request, resolver=public_resolver,
            url_validator=lambda url: not url.startswith('https://links.example/'))
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(calls, ['https://shop.example/item'])

    def test_dns_rebinding_and_multicast_are_rejected(self):
        for address in ['224.0.0.1', 'ff02::1', '::ffff:10.0.0.1', '100.64.0.1', '0.0.0.0']:
            with self.subTest(address=address):
                calls = []
                def resolver(*args, **kwargs):
                    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 443))]
                result = ui.suggest_title('https://shop.example/item', resolver=resolver, requester=lambda *args: calls.append(args))
                self.assertEqual(result['status'], 'unavailable')
                self.assertEqual(calls, [])

    def test_oversize_body_keeps_complete_metadata_in_bounded_prefix(self):
        body = '<h1>Capteur CO MOES</h1>' + 'x' * ui.MAX_HTML
        result = ui.suggest_title('https://shop.example/item', requester=lambda *args: reply(html=body), resolver=public_resolver)
        self.assertEqual(result['title'], 'Capteur CO MOES')
        self.assertTrue(result['diagnostics']['fetch']['truncated'])
        self.assertEqual(result['diagnostics']['fetch']['bytes_read'], ui.MAX_HTML)

    def test_dns_wait_is_bounded(self):
        def resolver(*args, **kwargs):
            time.sleep(.15)
            return public_resolver(*args, **kwargs)
        with patch.object(ui, 'TIMEOUT', .01):
            started = time.monotonic()
            result = ui.suggest_title('https://shop.example/item', resolver=resolver)
        self.assertEqual(result['status'], 'unavailable')
        self.assertLess(time.monotonic() - started, .12)

    def test_whole_redirect_chain_has_deadline(self):
        def request(*args):
            time.sleep(.03)
            return reply(302, location='/next')
        with patch.object(ui, 'TOTAL_TIMEOUT', .01):
            result = ui.suggest_title('https://shop.example/item', requester=request, resolver=public_resolver)
        self.assertEqual(result['status'], 'unavailable')

    def test_read_limit_and_declared_size_in_real_transport(self):
        class FakeResponse:
            status = 200
            fp = None
            def __init__(self, headers):
                self.headers = headers
            def getheader(self, name, default=''):
                return self.headers.get(name, default)
            def read1(self, size):
                return b'x' * size
            def close(self):
                pass
        class FakeConnection:
            sock = None
            closed = False
            def __init__(self, *args, **kwargs):
                pass
            def request(self, *args, **kwargs):
                pass
            def getresponse(self):
                return response
            def close(self):
                self.closed = True
        for headers in [{'Content-Length': '1000'}, {}, {'Content-Encoding': 'gzip'}]:
            response = FakeResponse(headers)
            with self.subTest(headers=headers), patch.object(ui, '_PinnedHTTPS', FakeConnection):
                if headers.get('Content-Encoding') == 'gzip':
                    with self.assertRaises(ui.InspectionError):
                        ui._request_once(ui._target('https://shop.example/item'), '93.184.216.34', 'GET', 100)
                else:
                    result = ui._request_once(ui._target('https://shop.example/item'), '93.184.216.34', 'GET', 100)
                    self.assertEqual(len(result.body), 100)
                    self.assertEqual(result.wire_bytes, 101)
                    self.assertTrue(result.truncated)

    def test_deadline_interrupts_a_stalled_detached_response_socket(self):
        stopped = threading.Event()
        class FakeSocket:
            def settimeout(self, timeout):
                pass
            def shutdown(self, how):
                stopped.set()
        class SlowResponse:
            status = 200
            fp = SimpleNamespace(raw=SimpleNamespace(_sock=FakeSocket()))
            closed = False
            def getheader(self, name, default=''):
                return 'text/html' if name == 'Content-Type' else default
            def read1(self, size):
                if not stopped.wait(1):
                    raise AssertionError('Global deadline did not interrupt the response')
                return b''
            def close(self):
                self.closed = True
        response = SlowResponse()
        class DetachedConnection:
            sock = None  # HTTPConnection detaches the socket for Connection: close.
            def __init__(self, *args, **kwargs):
                pass
            def request(self, *args, **kwargs):
                pass
            def getresponse(self):
                return response
            def close(self):
                pass
        with patch.object(ui, '_PinnedHTTPS', DetachedConnection), patch.object(ui, 'TOTAL_TIMEOUT', .05):
            result = ui.suggest_title('https://shop.example/item', resolver=public_resolver)
        self.assertTrue(stopped.is_set())
        self.assertTrue(response.closed)
        self.assertEqual(result['status'], 'unavailable')



class TitleEditorialTests(unittest.TestCase):
    def suggest(self, title, page='', status=200, url='https://shop.example/item'):
        return ui.suggest_title(url, current_title=title,
            requester=lambda *args: reply(status, html=page), resolver=public_resolver)

    def test_editorial_fixtures_and_idempotence(self):
        cases = json.loads((Path(__file__).parent / 'fixtures/title_editorial.json').read_text(encoding='utf-8'))
        for case in cases:
            with self.subTest(case=case['case']):
                result = self.suggest(case['current'], status=403)
                self.assertEqual(result['title'], case['expected'])
                self.assertEqual(result['diagnostics']['fetch']['code'], 'http_403')
                if case['current'] != case['expected']:
                    self.assertEqual((result['source'], result['status'], result['confidence']), ('editorial', 'ok', 'high'))
                    self.assertEqual(result['reason'], 'editorial_correction')
                    self.assertEqual(result['diagnostics']['destination_decision']['status'], 'unavailable')
                else:
                    self.assertNotEqual(result['status'], 'ok')
                    self.assertNotIn('editorial', result['diagnostics'])
                again = self.suggest(result['title'], status=403)
                self.assertEqual(again['title'], result['title'])
                self.assertNotEqual(again['status'], 'ok', 'Never repeatedly propose a corrected title')

    def test_editorial_works_without_reliable_destination(self):
        cases = [('', 'metadata_missing'), ('<title>Catalogue</title>', 'generic_metadata'),
                 ('<title>Robot check</title>', 'blocked_page'),
                 ('<h1>Capteur AQARA T1</h1><meta property="og:title" content="Caméra Reolink R2">', 'conflicting_metadata')]
        for page, reason in cases:
            with self.subTest(reason=reason):
                result = self.suggest('Capteur de temperature zigbee', page)
                self.assertEqual(result['title'], 'Capteur de température Zigbee')
                self.assertEqual(result['source'], 'editorial')
                self.assertEqual(result['diagnostics']['destination_decision']['reason'], reason)

    def test_equivalent_metadata_does_not_hide_existing_typo(self):
        result = self.suggest('home assistant green', '<h1>Home Assistant Green</h1>')
        self.assertEqual((result['title'], result['source']), ('Home Assistant Green', 'editorial'))
        self.assertEqual(result['diagnostics']['destination_decision']['status'], 'unchanged')

    def test_retained_title_can_be_corrected_without_losing_information(self):
        result = self.suggest('Capteur de temperature zigbee MOES ZC-HM', '<h1>Capteur MOES</h1>')
        self.assertEqual(result['title'], 'Capteur de température Zigbee MOES ZC-HM')
        self.assertEqual(result['diagnostics']['destination_decision']['status'], 'retained')

    def test_destination_enrichment_remains_distinct_and_prioritary(self):
        result = self.suggest('home assistant', '<h1>Home Assistant Green</h1>')
        self.assertEqual((result['title'], result['source'], result['status']), ('Home Assistant Green', 'heading', 'ok'))
        self.assertNotIn('editorial', result['diagnostics'])

    def test_network_and_security_errors_survive_editorial_correction(self):
        with patch.object(ui, '_fetch', side_effect=ui.InspectionError('secret', 'dns_error', 'dns')):
            result = self.suggest('Paye moi un cafe')
        self.assertEqual(result['title'], 'Paye-moi un café')
        self.assertEqual(result['diagnostics']['fetch']['code'], 'dns_error')
        self.assertNotIn('secret', json.dumps(result))
        calls = []
        result = ui.suggest_title('http://169.254.169.254/private?secret=1', current_title='home assistant green',
            requester=lambda *args: calls.append(args), resolver=public_resolver)
        self.assertEqual(calls, [])
        self.assertEqual(result['title'], 'Home Assistant Green')
        self.assertEqual(result['diagnostics']['fetch']['code'], 'blocked_destination')
        self.assertEqual(result['diagnostics']['destination_decision']['status'], 'unavailable')
        self.assertNotIn('169.254', json.dumps(result))
        self.assertNotIn('secret', json.dumps(result))

    def test_creation_does_not_use_editorial_fallback(self):
        result = self.suggest('', '<h1>home assistant green</h1>')
        self.assertEqual((result['title'], result['source']), ('home assistant green', 'heading'))
        self.assertNotIn('editorial', result['diagnostics'])

    def test_maximum_length_never_drops_reference(self):
        title = 'Paye moi un cafe'  # Hyphenation itself does not extend the title.
        self.assertEqual(ui._editorial_title(title)[0], 'Paye-moi un café')
        title = 'Capteur de temperature ' + 'x' * 136 + '!'
        self.assertEqual(len(title), 160)
        self.assertEqual(ui._editorial_title(title), (title, []))


if __name__ == '__main__':
    unittest.main()
