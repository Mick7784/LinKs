"""Offline, deterministic tests for the metadata/availability engine."""
import socket
import unittest

import url_inspection as ui


PUBLIC_IP = '93.184.216.34'


def public_resolver(host, port, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (PUBLIC_IP, port))]


def reply(status=200, html='', content_type='text/html; charset=utf-8', location=''):
    return ui.Response(status, content_type, html.encode('utf-8'), location)


class InspectorTests(unittest.TestCase):
    def test_product_json_ld_beats_og_and_adds_missing_brand(self):
        page = '''<html><head><meta property="og:title" content="Promotion exceptionnelle !">
        <script type="application/ld+json">{"@context":"https://schema.org","@graph":[
        {"@type":"WebPage","name":"Store"},
        {"@type":["Thing","Product"],"name":"OMVI X16 PoE, livraison gratuite", "brand":{"name":"Reolink"}}]}</script>
        <title>Un autre titre</title></head></html>'''
        calls = []
        def get(target, ip, method, limit):
            calls.append((target.url, ip, method, limit))
            return reply(html=page)
        result = ui.suggest_title('https://shop.reolink.com/camera', requester=get, resolver=public_resolver)
        self.assertEqual(result, {'title': 'Reolink OMVI X16 PoE', 'source': 'schema_product', 'status': 'ok', 'confidence': 'high', 'reason': 'more_informative'})
        self.assertEqual(calls[0][1:], (PUBLIC_IP, 'GET', ui.MAX_HTML))

    def test_meta_fallback_and_html_entities(self):
        text = '<meta property="og:title" content="UGREEN NASync DXP4800 Pro | Boutique officielle"><title>Autre</title>'
        result = ui.suggest_title('https://ugreen.com/product/1', requester=lambda *args: reply(html=text), resolver=public_resolver)
        self.assertEqual((result['title'], result['source']), ('UGREEN NASync DXP4800 Pro', 'open_graph'))
        result = ui.suggest_title('https://ugreen.com/product/1', requester=lambda *args: reply(html='<title>tado° Thermostat X &amp; capteur</title>'), resolver=public_resolver)
        self.assertEqual(result['title'], 'tado° Thermostat X & capteur')

    def test_product_type_full_schema_url(self):
        page = '<script type="application/ld+json">{"@type":"https://schema.org/Product","name":"Sonoff ZBMINIR2"}</script>'
        result = ui.suggest_title('https://sonoff.com/store/p', requester=lambda *args: reply(html=page), resolver=public_resolver)
        self.assertEqual(result['title'], 'Sonoff ZBMINIR2')

    def test_blocked_shop_falls_back_to_descriptive_url_slug(self):
        result = ui.suggest_title('https://example.com/products/ugreen-dxp4800-pro', requester=lambda *args: reply(403), resolver=public_resolver)
        self.assertEqual(result, {'title': 'ugreen dxp4800 pro', 'source': 'url_slug', 'status': 'ok', 'confidence': 'low', 'reason': 'more_informative'})

    def test_title_fallback_when_metadata_is_empty(self):
        result = ui.suggest_title('https://example.com/products/reolink-omvi-x16', requester=lambda *args: reply(html='<html></html>'), resolver=public_resolver)
        self.assertEqual(result, {'title': 'reolink omvi x16', 'source': 'url_slug', 'status': 'ok', 'confidence': 'low', 'reason': 'more_informative'})
        result = ui.suggest_title('https://example.com/dp/B0CWV1234', requester=lambda *args: reply(html='<html></html>'), resolver=public_resolver)
        self.assertEqual(result['title'], '')

    def test_redirects_validate_each_hostname_before_network_request(self):
        requested = []
        def get(target, ip, method, limit):
            requested.append((target.url, ip))
            return reply(status=302, location='http://127.0.0.1/secrets')
        result = ui.suggest_title('https://safe.example/product', requester=get, resolver=public_resolver)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(len(requested), 1)

    def test_dns_private_and_mixed_addresses_are_rejected(self):
        for bad in ['127.0.0.1', '10.1.2.3', '192.168.0.3', '169.254.169.254', '::1', '::ffff:127.0.0.1']:
            url = f'https://[{bad}]/' if ':' in bad else f'http://{bad}/'
            self.assertEqual(ui.check_destination(url, resolver=public_resolver)['status'], 'unknown')
        def mixed(host, port, **kwargs):
            return [(0, 0, 0, '', (PUBLIC_IP, port)), (0, 0, 0, '', ('10.0.0.1', port))]
        calls = []
        self.assertEqual(ui.check_destination('https://example.com', resolver=mixed,
                          requester=lambda *args: calls.append(args))['status'], 'unknown')
        self.assertEqual(calls, [])

    def test_bad_urls_and_forbidden_ports_cannot_be_fetched(self):
        urls = ['file:///etc/passwd', 'http://localhost/test', 'http://service.local/p',
                'http://example.com:8080/admin', 'https://u:pass@example.com/p',
                'http://example.com/hello\nHeader:evil', 'http://192.168.1.1/',
                'http://example.internal/path', 'https://[::1]/', 'ftp://example.com/a']
        calls = []
        for url in urls:
            self.assertEqual(ui.suggest_title(url, requester=lambda *args: calls.append(args), resolver=public_resolver)['status'], 'unavailable')
        self.assertEqual(calls, [])

    def test_follow_safe_redirect_and_keep_hostname_pin(self):
        calls = []
        def get(target, ip, method, size):
            calls.append((target.host, target.path, ip))
            return reply(301, location='https://store.example/products/item') if len(calls) == 1 else reply(html='<meta property="og:title" content="Caméra Reolink OMVI X16 PoE">')
        result = ui.suggest_title('https://example.com/start', requester=get, resolver=public_resolver)
        self.assertEqual(result['title'], 'Caméra Reolink OMVI X16 PoE')
        self.assertEqual(calls, [('example.com', '/start', PUBLIC_IP), ('store.example', '/products/item', PUBLIC_IP)])

    def test_loop_and_too_many_redirects_become_unknown(self):
        self.assertEqual(ui.check_destination('https://example.com/a', resolver=public_resolver,
                         requester=lambda *args: reply(301, location='/a'))['status'], 'unknown')
        count = [0]
        def moving(*args):
            count[0] += 1
            return reply(302, location='/path'+str(count[0]))
        self.assertEqual(ui.check_destination('https://example.com/a', requester=moving, resolver=public_resolver)['status'], 'unknown')
        self.assertEqual(count[0], ui.MAX_REDIRECTS + 1)

    def test_head_success_does_not_need_get(self):
        calls = []
        def request(target, ip, method, limit):
            calls.append(method)
            return reply(200)
        self.assertEqual(ui.check_destination('https://example.com', requester=request, resolver=public_resolver), {'status': 'valid', 'http_status': 200})
        self.assertEqual(calls, ['HEAD'])

    def test_head_404_get_200_does_not_false_alarm(self):
        calls = []
        def request(target, ip, method, limit):
            calls.append(method)
            return reply(404 if method == 'HEAD' else 200)
        self.assertEqual(ui.check_destination('https://example.com', requester=request, resolver=public_resolver)['status'], 'valid')
        self.assertEqual(calls, ['HEAD', 'GET'])

    def test_get_404_or_410_confirmed_broken(self):
        for code in [404, 410]:
            result = ui.check_destination('https://example.com', requester=lambda *args: reply(code), resolver=public_resolver)
            self.assertEqual(result, {'status': 'broken', 'http_status': code})

    def test_blocked_or_server_error_remains_unknown(self):
        for code in [401, 403, 429, 500, 503]:
            result = ui.check_destination('https://example.com', requester=lambda *args: reply(code), resolver=public_resolver)
            self.assertEqual(result, {'status': 'unknown', 'http_status': code})
        def fail(*args):
            raise socket.timeout()
        self.assertEqual(ui.check_destination('https://example.com', requester=fail, resolver=public_resolver)['status'], 'unknown')

    def test_binary_response_never_generates_a_title(self):
        result = ui.suggest_title('https://example.com/file.pdf', requester=lambda *args: reply(content_type='application/pdf'), resolver=public_resolver)
        self.assertEqual(result['title'], '')


if __name__ == '__main__':
    unittest.main()
