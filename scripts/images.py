"""Decode user raster images before storing them; never trust MIME alone."""
from io import BytesIO
import warnings
from PIL import Image, ImageFile

MAX_BYTES = 4 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_TOTAL_PIXELS = 64_000_000
FORMATS = {'png': 'PNG', 'jpg': 'JPEG', 'jpeg': 'JPEG', 'webp': 'WEBP', 'gif': 'GIF'}
ImageFile.LOAD_TRUNCATED_IMAGES = False


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
