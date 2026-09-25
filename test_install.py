import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import install


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.package = self.root / 'repository'
        self.package.mkdir()
        self.patcher = patch.object(install, 'ROOT', self.package)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def archive(self, name):
        archive = self.package / install.ARCHIVE
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr(name, 'fixture')
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        archive.with_suffix('.zip.sha256').write_text(checksum, encoding='ascii')
        return archive

    def test_portable_layout_detection(self):
        comfy = self.root / 'ComfyUI'
        (comfy / 'custom_nodes').mkdir(parents=True)
        (comfy / 'user').mkdir()
        self.assertEqual(install.find_comfy(), comfy)

    def test_archive_checksum_rejected(self):
        archive = self.archive('MiniMax-Director-Distribution/manage.py')
        archive.write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            install.unpack(self.root / 'unpacked')

    def test_archive_traversal_rejected(self):
        self.archive('../escape.py')
        with self.assertRaisesRegex(ValueError, 'outside'):
            install.unpack(self.root / 'unpacked')
        self.assertFalse((self.root / 'escape.py').exists())

    def test_valid_archive_unpacked(self):
        self.archive('MiniMax-Director-Distribution/manage.py')
        output = install.unpack(self.root / 'unpacked')
        self.assertEqual((output / 'manage.py').read_text(), 'fixture')


if __name__ == '__main__':
    unittest.main()
