"""Find a newer release on GitHub and download its installer."""
import hashlib
import json
import urllib.request

LATEST = 'https://api.github.com/repos/Ammaar-Alam/g2-bridge/releases/latest'
DOWNLOADS = 'https://github.com/Ammaar-Alam/g2-bridge/releases/download/'


def newer(version, current):
    def numbers(text):
        return tuple(int(part) for part in text.split('.'))
    return numbers(version) > numbers(current)


def find(current):
    """Return the version, installer URL, and SHA-256 of a release newer than current, or None."""
    request = urllib.request.Request(LATEST, headers={'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=10) as reply:
        release = json.load(reply)
    if not newer(release['tag_name'], current):
        return None
    for asset in release['assets']:
        digest = asset.get('digest') or ''
        if (asset['name'].endswith('-Setup.exe') and asset['browser_download_url'].startswith(DOWNLOADS)
                and digest.startswith('sha256:')):
            return dict(version=release['tag_name'], url=asset['browser_download_url'], sha256=digest[7:])
    return None


def download(update, folder):
    """Save the installer and return its path. A file that differs from the published SHA-256 is deleted."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/'GogglesBridge-Setup.exe'
    digest = hashlib.sha256()
    with urllib.request.urlopen(update['url'], timeout=30) as reply, path.open('wb') as file:
        while block := reply.read(1 << 20):
            digest.update(block)
            file.write(block)
    if digest.hexdigest() != update['sha256']:
        path.unlink()
        raise ValueError('The download does not match the published SHA-256')
    return path
