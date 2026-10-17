"""Decode user raster images before storing them; never trust MIME alone."""
from io import BytesIO
import warnings
from PIL import Image, ImageFile
import base64,re,xml.etree.ElementTree as ET

MAX_BYTES = 4 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_TOTAL_PIXELS = 64_000_000
FORMATS = {'png': 'PNG', 'jpg': 'JPEG', 'jpeg': 'JPEG', 'webp': 'WEBP', 'gif': 'GIF'}
ImageFile.LOAD_TRUNCATED_IMAGES = False

def validate_legacy_asset(raw,extension):
    """Portable historical SVG artwork, never executable markup or remote references.

    The upload endpoint remains raster-only. This contract is only for backups.
    """
    if extension.lower()!='.svg':return validate(raw,extension)
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:raise ValueError('Asset SVG trop volumineux')
    if re.search(br'<!\s*(DOCTYPE|ENTITY)\b',raw,re.I):raise ValueError('Déclarations SVG interdites')
    try:root=ET.fromstring(raw)
    except ET.ParseError:raise ValueError('SVG historique invalide') from None
    tags={'svg','g','defs','path','rect','circle','ellipse','line','polyline','polygon','text','tspan','title','desc','linearGradient','radialGradient','stop','clipPath','mask','symbol','use','image'}
    for node in root.iter():
        tag=node.tag.removeprefix('{http://www.w3.org/2000/svg}')
        if tag not in tags:raise ValueError('Élément SVG interdit')
        for attribute,value in node.attrib.items():
            if attribute.startswith('{') and not attribute.startswith('{http://www.w3.org/1999/xlink}') and attribute not in {'{http://www.w3.org/XML/1998/namespace}space','{http://www.w3.org/XML/1998/namespace}lang'}:raise ValueError('Attribut SVG interdit')
            key=attribute.removeprefix('{http://www.w3.org/1999/xlink}')
            if key.lower().startswith('on') or key in {'style','src'}:raise ValueError('Code SVG interdit')
            if key=='href' and not value.startswith('#'):
                match=re.fullmatch(r'data:image/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/=\s]+)',value)
                if tag!='image' or not match:raise ValueError('Référence SVG externe interdite')
                try:image=base64.b64decode(match[2],validate=True)
                except ValueError:raise ValueError('Image SVG invalide') from None
                validate(image,match[1])
            for reference in re.findall(r'url\((.*?)\)',value,re.I):
                if not re.fullmatch(r'\s*[\'"]?#[\w.-]+[\'"]?\s*',reference):raise ValueError('URL SVG externe interdite')
            if re.search(r'javascript\s*:|expression\s*\(',value,re.I):raise ValueError('Code SVG interdit')
    if root.tag not in {'svg','{http://www.w3.org/2000/svg}svg'}:raise ValueError('Racine SVG invalide')
    return {'format':'SVG'}


def validate(raw, extension, limit=MAX_BYTES):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= limit:
        raise ValueError('Image vide ou trop volumineuse')
    expected = FORMATS.get(extension.lower().lstrip('.'))
    if not expected:
        raise ValueError('Format image non pris en charge')
    if (expected == 'JPEG' and not raw.rstrip().endswith(b'\xff\xd9') or
        expected == 'GIF' and not raw.endswith(b';') or
        expected == 'WEBP' and (len(raw) < 12 or int.from_bytes(raw[4:8], 'little') + 8 > len(raw))):
        raise ValueError('Image tronquée')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw), formats=[expected]) as image:
                width, height = image.size
                if not 0 < width <= 8192 or not 0 < height <= 8192 or width * height > MAX_PIXELS:
                    raise ValueError('Image trop grande (8192 px et 16 millions de pixels maximum)')
                image.verify()
            # verify() checks structure/CRC; load() also validates compressed pixels.
            with Image.open(BytesIO(raw), formats=[expected]) as image:
                total = 0
                for index in range(getattr(image, 'n_frames', 1)):
                    image.seek(index)
                    total += image.width * image.height
                    if index >= 200 or total > MAX_TOTAL_PIXELS:
                        raise ValueError('Animation trop volumineuse')
                    image.load()
                return {'width': width, 'height': height, 'format': expected}
    except ValueError:
        raise
    except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Image corrompue, tronquée ou incompatible avec le format annoncé') from exc
