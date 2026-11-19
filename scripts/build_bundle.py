#!/usr/bin/env python3
"""Discover, validate and atomically publish Stromschlag's public Windows VST3 bundle."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone

OWNER = 'StromschlagProductions'
VENDOR = 'Stromschlag Audio'
ARCHIVE = 'Stromschlag-Audio-Plugin-Bundle.zip'
MANIFEST = 'bundle-manifest.json'
MAX_ZIP = 128 * 1024 * 1024
MAX_CONTENT = 512 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def api(path):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Stromschlag-Bundle',
               'X-GitHub-Api-Version': '2022-11-28'}
    if os.environ.get('GH_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
    req = urllib.request.Request('https://api.github.com/' + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def download(url, limit=MAX_ZIP):
    # Public browser URLs only; never forward an API credential to asset/CDN hosts.
    if not url.startswith(f'https://github.com/{OWNER}/'):
        raise ValueError('Unexpected asset origin')
    with urllib.request.urlopen(url, timeout=120) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Asset too large')
    return data


def repositories():
    page = 1
    while True:
        rows = api(f'users/{OWNER}/repos?type=owner&per_page=100&page={page}')
        if not rows:
            return
        yield from (r for r in rows if not r['private'] and not r['fork'])
        if len(rows) < 100:
            return
        page += 1


def choose_asset(release, product):
    if release['draft'] or release['prerelease'] or not release.get('published_at'):
        raise ValueError('Not a published stable release')
    choices = [a for a in release['assets'] if a.get('state') == 'uploaded'
               and re.match(re.escape(product) + r'[-_]', a['name'], re.I)
               and a['name'].lower().endswith('.zip')
               and re.search(r'windows|win64|win-x64', a['name'], re.I)
               and re.search(r'vst3', a['name'], re.I)
               and not re.search(r'arm64|win32|debug|test|source', a['name'], re.I)]
    if len(choices) != 1:
        raise ValueError('Expected exactly one Windows VST3 ZIP')
    a = choices[0]
    expected = f'https://github.com/{OWNER}/{release["_repository"]}/releases/download/'
    if not a['browser_download_url'].startswith(expected) or not 0 < a['size'] <= MAX_ZIP:
        raise ValueError('Unexpected release asset')
    return a


def relaxed_json(text):
    # Steinberg/JUCE moduleinfo permits trailing commas. Do not alter string contents.
    out, quoted, escaped = [], False, False
    for i, c in enumerate(text):
        if not quoted and c == ',' and text[i+1:].lstrip().startswith(('}', ']')):
            continue
        out.append(c)
        if quoted:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
    return json.loads(''.join(out))


def normalized_version(v):
    if not re.fullmatch(r'v?\d+(?:\.\d+)*', v):
        raise ValueError('Expected numeric stable version')
    parts = list(map(int, v.lstrip('v').split('.')))
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return parts


def validate_zip(data, product, version):
    files, seen, total = {}, set(), 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            name = info.filename
            parts = name.rstrip('/').split('/')
            if (not name or '\\' in name or any(p in ('', '.', '..') for p in parts)
                    or any(re.search(r'[<>:\"|?*\x00-\x1f]', p) or p.endswith((' ', '.')) or p.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(1,10)), *('LPT'+str(i) for i in range(1,10))} for p in parts)
                    or name.startswith('/') or info.flag_bits & 1
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError('Unsafe ZIP member: ' + name)
            key = name.rstrip('/').casefold()
            if key in seen:
                raise ValueError('Duplicate ZIP member')
            seen.add(key)
            total += info.file_size
            if total > MAX_CONTENT or info.file_size > MAX_CONTENT:
                raise ValueError('Expanded ZIP too large')
            if not info.is_dir():
                files[name] = z.read(info)  # decompress fully and verify CRC
    root = product + '.vst3'
    roots = {n.split('/')[0] for n in files if n.split('/')[0].lower().endswith('.vst3')}
    if roots != {root}:
        raise ValueError('Expected one directly installable VST3 directory')
    module = root + '/Contents/x86_64-win/' + product + '.vst3'
    metadata = root + '/Contents/Resources/moduleinfo.json'
    binary = files.get(module, b'')
    if len(binary) < 64 or binary[:2] != b'MZ':
        raise ValueError('Missing Windows module')
    pe = struct.unpack_from('<I', binary, 0x3c)[0]
    if binary[pe:pe+4] != b'PE\x00\x00' or len(binary) < pe + 6 or struct.unpack_from('<H', binary, pe+4)[0] != 0x8664:
        raise ValueError('Module is not Windows AMD64')
    m = relaxed_json(files.get(metadata, b'').decode('utf-8-sig'))
    classes = [c for c in m.get('Classes', []) if c.get('Category') == 'Audio Module Class']
    if (m.get('Name') != product or m.get('Factory Info', {}).get('Vendor') != VENDOR
            or not classes or any(c.get('Vendor') != VENDOR for c in classes)
            or normalized_version(m.get('Version', '')) != normalized_version(version)):
        raise ValueError('VST3 identity/version mismatch')
    cids = [c['CID'].upper() for c in classes]
    if any(not re.fullmatch(r'[0-9A-F]{32}', c) for c in cids) or len(set(cids)) != len(cids):
        raise ValueError('Invalid/duplicate audio class identity')
    result = {n: b for n, b in files.items() if n.startswith(root + '/')}
    # Preserve legal notices supplied outside the module; do not nest download ZIPs.
    for n, b in files.items():
        if '/' not in n and re.search(r'license|licence|notice|copying', n, re.I):
            result[f'LIZENZEN/{product}/{n}'] = b
    return result, cids


def previous_manifest(repo):
    release = api(f'repos/{repo}/releases/latest')
    if release is None:
        return None
    assets = [a for a in release['assets'] if a['name'] == MANIFEST]
    if len(assets) != 1:
        raise ValueError('Latest website release has no bundle manifest')
    return json.loads(download(assets[0]['browser_download_url'], 1024 * 1024))


def snapshot(out, previous=None):
    known = {p['repository'] for p in (previous or {}).get('plugins', [])}
    found, skipped = [], []
    for repo in sorted(repositories(), key=lambda r: r['name'].casefold()):
        name = repo['name']
        try:
            release = api(f'repos/{OWNER}/{name}/releases/latest')
            if release is None:
                if name in known:
                    raise ValueError('Previously bundled plugin has no stable release')
                continue
            release['_repository'] = name
            ref = urllib.parse.quote(release['tag_name'], safe='')
            cmake = api(f'repos/{OWNER}/{name}/contents/CMakeLists.txt?ref={ref}')
            text = base64.b64decode(cmake['content']).decode() if cmake and cmake.get('type') == 'file' else ''
            match = re.search(r'juce_add_plugin\s*\(\s*([A-Za-z][A-Za-z0-9_]*)', text)
            if not match or 'VST3' not in text or not re.search(r'COMPANY_NAME\s+"Stromschlag Audio"', text):
                raise ValueError('Not a qualifying Stromschlag JUCE VST3 project')
            product = match[1]
            asset = choose_asset(release, product)
            found.append(dict(repository=name, product=product, version=release['tag_name'],
                              release_id=release['id'], asset_id=asset['id'], asset_name=asset['name'],
                              asset_size=asset['size'], asset_updated_at=asset['updated_at'],
                              digest=asset.get('digest'), url=asset['browser_download_url']))
        except (ValueError, KeyError, UnicodeError) as e:
            if name in known:
                raise ValueError(f'Existing plugin {name}: {e}') from e
            skipped.append(f'{name}: {e}')
    if not known.issubset({p['repository'] for p in found}):
        raise ValueError('Previously bundled plugin disappeared from discovery')
    return found, skipped


def build(out, previous=None):
    out.mkdir(parents=True, exist_ok=True)
    plugins, skipped = snapshot(out, previous)
    cache = out / 'cache'
    cache.mkdir(exist_ok=True)
    entries, accepted, identities, roots = {}, [], set(), set()
    for p in plugins:
        known = p['repository'] in {x['repository'] for x in (previous or {}).get('plugins', [])}
        try:
            cached = cache / f'{p["asset_id"]}-{p["asset_updated_at"].replace(":", "")}.zip'
            data = cached.read_bytes() if cached.exists() else download(p['url'])
            if len(data) != p['asset_size']:
                raise ValueError('Truncated asset')
            digest = sha(data)
            if p['digest'] and p['digest'] != 'sha256:' + digest:
                raise ValueError('GitHub SHA256 mismatch')
            files, cids = validate_zip(data, p['product'], p['version'])
            root = (p['product'] + '.vst3').casefold()
            if root in roots or identities.intersection(cids):
                raise ValueError('Conflicting VST3 directory or class identity')
            roots.add(root)
            identities.update(cids)
            if set(n.casefold() for n in files).intersection(n.casefold() for n in entries):
                raise ValueError('Conflicting package path')
            entries.update(files)
            cached.write_bytes(data)
            p['sha256'] = digest
            accepted.append(p)
        except (ValueError, KeyError, UnicodeError, zipfile.BadZipFile, struct.error) as e:
            if known:
                raise ValueError(f'Existing plugin {p["repository"]}: {e}') from e
            skipped.append(f'{p["repository"]}: {e}')
    if not accepted:
        raise ValueError('No validated plugins; refusing empty bundle')
    identity = dict(builder=sha(Path(__file__).read_bytes()), plugins=accepted)
    fingerprint = sha(json.dumps(identity, sort_keys=True).encode())
    if previous and previous.get('fingerprint') == fingerprint:
        print('UNCHANGED: no new release needed')
        return None
    now = datetime.now(timezone.utc).isoformat()
    manifest = dict(schema=1, fingerprint=fingerprint, created_at=now, plugins=accepted, skipped=skipped)
    versions = ['STROMSCHLAG AUDIO – PLUGIN BUNDLE', 'Erstellt (UTC): ' + now, '']
    for p in accepted:
        versions += [f'{p["product"]}: {p["version"]}', f'https://github.com/{OWNER}/{p["repository"]}', '']
    entries['VERSIONEN.txt'] = '\n'.join(versions).encode()
    entries[MANIFEST] = json.dumps(manifest, indent=2, ensure_ascii=False).encode()
    entries['INSTALLATION.txt'] = ('STROMSCHLAG AUDIO – Installation unter Windows x64\n\n'
        'DAW schließen und dieses ZIP vollständig entpacken. Alle enthaltenen .vst3-Ordner\n'
        'gemeinsam auswählen und vollständig nach C:\\Program Files\\Common Files\\VST3\\ kopieren.\n'
        'Vorhandene gleichnamige Plugin-Ordner nach Sicherung der bisherigen Version ersetzen;\n'
        'nicht nur die inneren Moduldateien kopieren. DAW öffnen und ggf. Plugins neu scannen.\n'
        'Versionsübersicht: VERSIONEN.txt. Rechtliche Hinweise ggf. im Ordner LIZENZEN.\n'
        'Es wird kein zusätzlicher Plugins-, Windows- oder Versions-Unterordner benötigt.\n').encode()
    target = out / ARCHIVE
    temp = out / (ARCHIVE + '.tmp')
    with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for n, data in sorted(entries.items()):
            z.writestr(n, data)
    with zipfile.ZipFile(temp) as z:
        if z.testzip() is not None or set(z.namelist()) != set(entries):
            raise ValueError('Final ZIP verification failed')
        for p in accepted:
            validate_zip(_product_zip(entries, p['product']), p['product'], p['version'])
    temp.replace(target)
    (out / MANIFEST).write_bytes(entries[MANIFEST])
    (out / 'SHA256SUMS.txt').write_text(f'{sha(target.read_bytes())}  {ARCHIVE}\n{sha(entries[MANIFEST])}  {MANIFEST}\n')
    print(f'BUILT: {len(accepted)} plugins; ' + fingerprint)
    for reason in skipped:
        print('SKIPPED: ' + reason)
    return manifest


def _product_zip(entries, product):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for n, b in entries.items():
            if n.startswith(product + '.vst3/'):
                z.writestr(n, b)
    return buf.getvalue()


def publish(out, manifest, repo):
    tag = 'bundle-' + manifest['fingerprint'][:24]
    def gh(*args):
        return subprocess.check_output(['gh', *args, '--repo', repo], text=True)
    existing = api(f'repos/{repo}/releases/tags/{tag}')
    if existing and not existing['draft']:
        raise ValueError('Fingerprint already published; refusing to overwrite')
    notes = out / 'release-notes.txt'
    notes.write_text('Automatisch geprüftes Windows-x64-VST3-Bundle.\n\n' + '\n'.join(
        f'- {p["product"]} {p["version"]}' for p in manifest['plugins']) + '\n\nInstallation und Versionen stehen im ZIP.\n')
    if not existing:
        gh('release', 'create', tag, '--draft', '--target', os.environ['GITHUB_SHA'],
           '--title', 'Stromschlag Audio Plugin Bundle', '--notes-file', str(notes))
    paths = [out / ARCHIVE, out / MANIFEST, out / 'SHA256SUMS.txt']
    gh('release', 'upload', tag, *map(str, paths), '--clobber')
    with tempfile.TemporaryDirectory() as folder:
        gh('release', 'download', tag, '--dir', folder)
        for p in paths:
            if sha((Path(folder) / p.name).read_bytes()) != sha(p.read_bytes()):
                raise ValueError('Uploaded release verification failed')
    # Only a fully uploaded and re-downloaded draft becomes the public latest release.
    gh('release', 'edit', tag, '--draft=false', '--latest')
    print(f'PUBLISHED: https://github.com/{repo}/releases/tag/{tag}')


def keepalive(repo):
    # GitHub disables scheduled workflows in public repos after 60 inactive days.
    # A bounded heartbeat keeps discovery available even during a long release pause.
    commit = api(f'repos/{repo}/commits/main')
    last = datetime.fromisoformat(commit['commit']['committer']['date'].replace('Z', '+00:00'))
    if (datetime.now(timezone.utc) - last).days < 45:
        return
    path = '.github/bundle-heartbeat.txt'
    existing = api(f'repos/{repo}/contents/{path}')
    payload = dict(message='Keep automatic bundle discovery active',
                   content=base64.b64encode((datetime.now(timezone.utc).isoformat()+'\n').encode()).decode(), branch='main')
    if existing:
        payload['sha'] = existing['sha']
    subprocess.run(['gh', 'api', '--method', 'PUT', f'repos/{repo}/contents/{path}', '--input', '-'],
                   input=json.dumps(payload), text=True, check=True, stdout=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path('bundle-output'))
    parser.add_argument('--repo', default=OWNER + '/' + OWNER + '.github.io')
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--keepalive', action='store_true')
    args = parser.parse_args()
    previous = json.loads(args.previous.read_text()) if args.previous else previous_manifest(args.repo)
    result = build(args.out, previous)
    if result and args.publish:
        publish(args.out, result, args.repo)
    if args.keepalive and args.publish:
        keepalive(args.repo)


if __name__ == '__main__':
    main()
