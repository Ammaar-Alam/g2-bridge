"""Build the macOS app in dist/ and its disk image.

Needs the packages in requirements-app.txt plus PyInstaller, and Apple's command-line developer tools.
Signs with the first Developer ID Application certificate in the keychain, or GOGGLES_SIGNING_IDENTITY,
and ad-hoc without one. Set GOGGLES_NOTARY_PROFILE to a notarytool keychain profile to notarize.
"""
import hashlib
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from goggles_bridge import __version__
from goggles_bridge.app.backend import APP_NAME
from goggles_bridge.mac_capture import MIN_MACOS, SOURCE

BUNDLE_ID = 'io.github.ammaar-alam.goggles-bridge'
MINIMUM = '.'.join(map(str, MIN_MACOS))
# built from source so it loads on the oldest supported macOS, which Homebrew's copy does not
LIBUSB = 'libusb-1.0.30'
LIBUSB_URL = f'https://github.com/libusb/libusb/releases/download/v1.0.30/{LIBUSB}.tar.bz2'
LIBUSB_SHA256 = 'fea36f34f9156400209595e300840767ab1a385ede1dc7ee893015aea9c6dbaf'
NOTICES = f'''{APP_NAME} is licensed under the GNU General Public License v3.0. See LICENSE.txt.
Source code: https://github.com/Ammaar-Alam/g2-bridge

This app includes:
- libusb ({LIBUSB}), licensed under the GNU LGPL v2.1. Source: {LIBUSB_URL}
- PyUSB, pywebview, PyObjC, and Python, under their own licenses.
'''


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def run(*command, **options):
    subprocess.run([str(part) for part in command], check=True, **options)


def signing_identity():
    if os.environ.get('GOGGLES_SIGNING_IDENTITY'):
        return os.environ['GOGGLES_SIGNING_IDENTITY']
    listed = subprocess.run(['security', 'find-identity', '-v', '-p', 'codesigning'], capture_output=True, text=True).stdout
    found = re.search(r'"(Developer ID Application: [^"]+)"', listed)
    return found.group(1) if found else '-'


def libusb(cache):
    """Return the folder holding libusb-1.0.dylib, building it once per release."""
    prefix = cache/f'{LIBUSB}-macos{MINIMUM}-arm64'
    if (prefix/'lib'/'libusb-1.0.dylib').is_file():
        return prefix/'lib'
    archive = cache/f'{LIBUSB}.tar.bz2'
    if not archive.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        print(f'Downloading {LIBUSB_URL}', flush=True)
        urllib.request.urlretrieve(LIBUSB_URL, archive)
    if sha256(archive) != LIBUSB_SHA256:
        raise SystemExit(f'{archive} does not match the pinned libusb checksum. Delete it and build again')
    with tempfile.TemporaryDirectory() as work, tarfile.open(archive) as source:
        source.extractall(work, filter='data')
        flags = f'-arch arm64 -mmacosx-version-min={MINIMUM}'
        # pipe2 is newer than the oldest supported macOS, so keep libusb on its pipe fallback
        env = dict(os.environ, CFLAGS=flags, LDFLAGS=flags, ac_cv_func_pipe2='no')
        folder = Path(work)/LIBUSB
        run('./configure', f'--prefix={prefix}', '--disable-static', cwd=folder, env=env)
        run('make', f'-j{os.cpu_count()}', 'install', cwd=folder, env=env)
    return prefix/'lib'


def sign(path, identity, *extra):
    hardened = ('--options', 'runtime', '--timestamp') if identity != '-' else ()
    run('codesign', '--force', '--sign', identity, *hardened, *extra, path)


def main():
    dist, build, cache = ROOT/'dist', ROOT/'build', ROOT/'packaging'/'cache'
    app = dist/f'{APP_NAME}.app'
    identity = signing_identity()
    libraries = libusb(cache)
    build.mkdir(exist_ok=True)
    helper = build/'mac-capture'
    run('xcrun', 'swiftc', '-O', '-target', f'arm64-apple-macos{MINIMUM}', '-o', helper, SOURCE)
    # PyObjC's callbacks need writable code memory under the hardened runtime
    entitlements = ROOT/'packaging'/'entitlements.plist'
    signed = ('--codesign-identity', identity, '--osx-entitlements-file', entitlements) if identity != '-' else ()
    # PyUSB's PyInstaller hook bundles whichever libusb it loads, so point it at the one built above
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--name', APP_NAME,
        '--icon', ROOT/'packaging'/'goggles-bridge.icns', '--osx-bundle-identifier', BUNDLE_ID,
        '--target-architecture', 'arm64', *signed,
        '--add-data', f"{ROOT/'goggles_bridge'/'app'/'ui'}:goggles_bridge/app/ui", '--add-binary', f'{helper}:.',
        '--hidden-import', 'usb.backend.libusb1',
        '--distpath', dist, '--workpath', build, '--specpath', build, ROOT/'scripts'/'goggles_bridge_app.py',
        cwd=ROOT, env=dict(os.environ, DYLD_LIBRARY_PATH=str(libraries)))

    info_path = app/'Contents'/'Info.plist'
    info = plistlib.loads(info_path.read_bytes())
    # the interface is light only, so keep the title bar light in dark mode too
    info.update(CFBundleShortVersionString=__version__, CFBundleVersion=__version__, LSMinimumSystemVersion=MINIMUM,
                NSRequiresAquaSystemAppearance=True)
    info_path.write_bytes(plistlib.dumps(info))
    resources = app/'Contents'/'Resources'
    shutil.copyfile(ROOT/'LICENSE', resources/'LICENSE.txt')
    (resources/'NOTICES.txt').write_text(NOTICES, encoding='utf-8')
    sign(app, identity, '--entitlements', entitlements)  # again, to seal the edited Info.plist and notices
    run('codesign', '--verify', '--deep', '--strict', app)

    image = dist/f'GogglesBridge-{__version__}.dmg'
    image.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as staging:
        run('ditto', app, Path(staging)/app.name)
        (Path(staging)/'Applications').symlink_to('/Applications')
        run('hdiutil', 'create', '-volname', APP_NAME, '-srcfolder', staging, '-format', 'UDZO', '-quiet', image)
    if identity == '-':
        print(f'Built {image} with an ad-hoc signature. macOS asks again for screen recording after each build')
    else:
        sign(image, identity)
        profile = os.environ.get('GOGGLES_NOTARY_PROFILE')
        if profile:
            run('xcrun', 'notarytool', 'submit', image, '--keychain-profile', profile, '--wait')
            run('xcrun', 'stapler', 'staple', image)
            run('spctl', '--assess', '--type', 'open', '--context', 'context:primary-signature', '--verbose', image)
        else:
            print('Set GOGGLES_NOTARY_PROFILE to notarize. Without it, Gatekeeper blocks the first launch')
    print(f'Built {image}\nSHA-256: {sha256(image)}')


if __name__ == '__main__':
    main()
