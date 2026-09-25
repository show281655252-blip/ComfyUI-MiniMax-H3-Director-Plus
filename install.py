"""Install the bundled Director patch without manually extracting its ZIP."""
import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARCHIVE = 'MiniMax-Director-Distribution-0.1.0-rc1.zip'


def find_comfy():
    for parent in (ROOT, *ROOT.parents):
        for candidate in (parent, parent / 'ComfyUI'):
            if (candidate / 'custom_nodes').is_dir() and (candidate / 'user').is_dir():
                return candidate
    return None


def unpack(destination):
    archive = ROOT / ARCHIVE
    expected = (ROOT / (ARCHIVE + '.sha256')).read_text(encoding='ascii').split()[0]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError('Archive checksum mismatch. Restore the ZIP and checksum from the repository.')
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError('Archive path outside extraction directory.')
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Archive symbolic links are not supported.')
        source.extractall(destination)
    return destination / 'MiniMax-Director-Distribution'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'install', 'rollback'], nargs='?', default='check')
    parser.add_argument('--comfy', type=Path, help='ComfyUI folder; detected automatically when this repository is inside or beside it')
    parser.add_argument('--backup', type=Path, help='Backup folder for rollback')
    args = parser.parse_args()
    comfy = args.comfy or find_comfy()
    if comfy is None:
        parser.error('Cannot find ComfyUI. Add --comfy "path/to/ComfyUI".')
    comfy = comfy.resolve()
    with tempfile.TemporaryDirectory(prefix='director-install-') as temporary:
        package = unpack(Path(temporary))
        command = [sys.executable, '-X', 'utf8', str(package / 'manage.py'), '--comfy', str(comfy), args.action]
        if args.backup:
            command += ['--backup', str(args.backup.resolve())]
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        # The bundled manager's relative recovery command must name this persistent wrapper.
        print(result.stdout.replace('python manage.py', 'python install.py'), end='')
        if result.stderr:
            print(result.stderr, file=sys.stderr, end='')
        if result.returncode:
            return result.returncode
        if args.action == 'install':
            example = ROOT / 'workflows/Director_Long_Video_HyperFlow.json'
            if not example.exists():
                example.parent.mkdir(exist_ok=True)
                shutil.copyfile(package / 'workflows' / example.name, example)
            print(f'Open this workflow in ComfyUI: {example}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
