import unittest
from io import BytesIO
from PIL import Image
import images


def raster(format='PNG', size=(12, 9)):
    stream=BytesIO();Image.new('RGB',size,'#337799').save(stream,format=format)
    return stream.getvalue()


class ImageTests(unittest.TestCase):
    def test_supported_formats_and_real_pixels(self):
        for ext,format in images.FORMATS.items():
            with self.subTest(ext=ext):
                self.assertEqual(images.validate(raster(format),ext)['width'],12)
    def test_rejects_fake_mismatched_truncated_and_oversized(self):
        for raw,ext in [(b'\x89PNG\r\n\x1a\n','png'),(b'<html>fake</html>','png'),
                        (raster('PNG'),'jpg'),(raster('PNG')[:40],'png'),(raster('JPEG')[:-30],'jpg'),
                        (raster('WEBP')[:20],'webp'),(raster('GIF')[:20],'gif'),(raster(size=(8193,1)),'png')]:
            with self.subTest(ext=ext,length=len(raw)),self.assertRaises(ValueError):images.validate(raw,ext)
        with self.assertRaises(ValueError):images.validate(raster(),'png',limit=10)
    def test_png_bad_crc(self):
        raw=bytearray(raster());raw[-15]^=1
        with self.assertRaises(ValueError):images.validate(bytes(raw),'png')

if __name__=='__main__':unittest.main()
