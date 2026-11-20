#!/usr/bin/env python3
"""Draft a homepage card for any released, qualifying plugin that index.html
does not yet list, and open a pull request for human review.

Reuses the discovery/validation building blocks from build_bundle.py (same
repository listing, same CMakeLists.txt/VST3/COMPANY_NAME check) so a new
plugin only needs the usual Stromschlag conventions, no extra configuration.

This never writes to main directly and never merges: it only opens (or
updates) a PR. Wording, category label and screenshot choice are drafted
heuristically from the plugin's own README and are meant to be checked by a
human before merging - see the PR body.
"""
import argparse
import base64
import html
import json
import re
import subprocess
import sys
from pathlib import Path

from build_bundle import OWNER, VENDOR, api, repositories

ARTICLE_MARKER = 'data-release-repo="{repo}"'
PLUGINS_CLOSE = '</div><div class="plugin-quality"'
BRANCH_PREFIX = 'plugin-card/'


def existing_card_repos(html_text):
    return set(re.findall(r'data-release-repo="([^"]+)"', html_text))


def product_name(cmake_text):
    m = re.search(r'juce_add_plugin\s*\(\s*([A-Za-z][A-Za-z0-9_]*)', cmake_text)
    return m[1] if m else None


def qualifies(repo_name):
    """Mirror build_bundle's discovery check: published stable release +
    a CMakeLists.txt at that tag with juce_add_plugin/VST3/COMPANY_NAME."""
    release = api(f'repos/{OWNER}/{repo_name}/releases/latest')
    if release is None or release.get('draft') or release.get('prerelease'):
        return None
    tag = release['tag_name']
    ref = tag.replace('/', '%2F')
    cmake = api(f'repos/{OWNER}/{repo_name}/contents/CMakeLists.txt?ref={ref}')
    if not cmake or cmake.get('type') != 'file':
        return None
    text = base64.b64decode(cmake['content']).decode('utf-8', 'replace')
    product = product_name(text)
    if not product or 'VST3' not in text or not re.search(r'COMPANY_NAME\s+"' + re.escape(VENDOR) + '"', text):
        return None
    return dict(repo=repo_name, product=product, tag=tag, ref=ref)


def fetch_text(repo_name, path, ref):
    data = api(f'repos/{OWNER}/{repo_name}/contents/{path}?ref={ref}')
    if not data or data.get('type') != 'file':
        return None
    return base64.b64decode(data['content']).decode('utf-8', 'replace')


def screenshot_url(repo_name, ref):
    """Prefer a committed docs/oberflaeche-*.png at the release tag (the
    convention every existing card already uses); skip the card if none
    exists yet, rather than guess a filename that 404s."""
    listing = api(f'repos/{OWNER}/{repo_name}/contents/docs?ref={ref}')
    if not isinstance(listing, list):
        return None
    for name in ('oberflaeche-dunkel.png', 'oberflaeche-hell.png'):
        if any(e['name'] == name for e in listing):
            return f'https://raw.githubusercontent.com/{OWNER}/{repo_name}/{ref}/docs/{name}'
    for entry in listing:
        if re.fullmatch(r'oberflaeche-[a-z]+\.png', entry['name']):
            return f'https://raw.githubusercontent.com/{OWNER}/{repo_name}/{ref}/docs/{entry["name"]}'
    return None


def strip_markdown(text):
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = re.sub(r'\*\*([^*]*)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]*)\*', r'\1', text)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    return text.strip()


def draft_copy(readme):
    """Heuristic only (see module docstring): title line '# NAME - Subtitle',
    then the first plain paragraph as the description. A human reviews both
    in the PR; this is a starting draft, not a final choice of words."""
    lines = [l.rstrip() for l in readme.splitlines()]
    name, subtitle = None, ''
    for line in lines:
        if line.startswith('# '):
            heading = line[2:].strip()
            parts = re.split(r'\s+[–—-]\s+', heading, maxsplit=1)
            name = parts[0].strip()
            subtitle = parts[1].strip() if len(parts) > 1 else ''
            break
    if not name:
        return None
    desc = ''
    in_body = False
    for line in lines:
        s = line.strip()
        if s.startswith('# '):
            in_body = True
            continue
        if not in_body:
            continue
        if not s or s.startswith(('<', '#', '**', '[', '!', '|', '-')):
            continue
        desc = strip_markdown(s)
        break
    return dict(name=name, subtitle=subtitle, desc=desc)


def build_article(info, copy, image_url):
    repo = info['repo']
    name = html.escape(copy['name'])
    subtitle = html.escape(copy['subtitle'])
    desc = html.escape(copy['desc']) or '(Beschreibung bitte ergaenzen.)'
    img = html.escape(image_url)
    return (
        f'<article class="plugin"><div class="visual"><img loading="lazy" src="{img}" '
        f'alt="{name} – Bedienoberfläche"></div><div class="info">'
        f'<span class="num">NN / KATEGORIE PRÜFEN</span><h3>{name}</h3>'
        f'<p class="subtitle">{subtitle}</p><p class="desc">{desc}</p>'
        f'<div class="buttons"><a class="btn primary" '
        f'href="https://github.com/{OWNER}/{repo}/releases/latest" data-release-repo="{repo}">'
        f'↓ Herunterladen</a><a class="btn secondary" href="https://github.com/{OWNER}/{repo}">'
        f'Details &amp; Quellcode</a><span class="version" hidden>Aktuelle Version'
        f'<strong data-version-of="{repo}"></strong></span></div></div></article>'
    )


def next_number(html_text):
    nums = [int(m) for m in re.findall(r'<span class="num">(\d+)\s*/', html_text)]
    return (max(nums) + 1) if nums else 1


def gh(*args, **kwargs):
    return subprocess.run(['gh', *args], check=True, text=True, **kwargs)


def open_pr_for(repo_name, index_path):
    branch = BRANCH_PREFIX + repo_name.lower()
    full_repo = f'{OWNER}/{OWNER}.github.io'
    existing = subprocess.run(
        ['gh', 'pr', 'list', '--repo', full_repo, '--head', branch, '--state', 'open', '--json', 'number'],
        check=True, text=True, capture_output=True).stdout
    if json.loads(existing):
        print(f'SKIP {repo_name}: offener Entwurf existiert bereits ({branch})')
        return False

    info = qualifies(repo_name)
    if not info:
        return False
    html_text = index_path.read_text(encoding='utf-8')
    if repo_name in existing_card_repos(html_text):
        return False

    readme = fetch_text(repo_name, 'README.md', info['ref'])
    if not readme:
        print(f'SKIP {repo_name}: kein README.md am Release-Tag')
        return False
    copy = draft_copy(readme)
    if not copy:
        print(f'SKIP {repo_name}: Titelzeile in README.md nicht gefunden')
        return False
    image = screenshot_url(repo_name, info['ref'])
    if not image:
        print(f'SKIP {repo_name}: kein docs/oberflaeche-*.png am Release-Tag gefunden')
        return False

    article = build_article(info, copy, image).replace(
        'NN / KATEGORIE PRÜFEN', f'{next_number(html_text):02d} / KATEGORIE PRÜFEN')
    if PLUGINS_CLOSE not in html_text:
        print('SKIP: Einfuegestelle in index.html nicht gefunden (Layout geaendert?)')
        return False
    html_text = html_text.replace(PLUGINS_CLOSE, article + PLUGINS_CLOSE, 1)
    index_path.write_text(html_text, encoding='utf-8')

    gh('api', f'repos/{OWNER}/{OWNER}.github.io', '--jq', '.default_branch')  # fail fast if no access
    subprocess.run(['git', 'checkout', '-B', branch], check=True)
    subprocess.run(['git', 'add', str(index_path)], check=True)
    subprocess.run(['git', '-c', 'user.name=stromschlag-bot', '-c', 'user.email=bot@stromschlagaudio.invalid',
                     'commit', '-m', f'Entwurf: Plugin-Kachel fuer {copy["name"]}'], check=True)
    subprocess.run(['git', 'push', '-f', 'origin', branch], check=True)
    body = (
        f'Automatisch erzeugter Entwurf, weil `{repo_name}` ein gueltiges Release hat '
        f'(Tag `{info["tag"]}`, Produkt `{info["product"]}`), aber noch keine Kachel auf der Startseite.\n\n'
        '**Bitte vor dem Merge pruefen:**\n'
        '- Kategorie-Nummer/-Label (`KATEGORIE PRUEFEN` ist nur ein Platzhalter)\n'
        '- Beschreibungstext (aus dem ersten Absatz des README geraten, nicht redigiert)\n'
        '- Gewaehltes Screenshot-Bild (Dunkel bevorzugt, falls vorhanden)\n\n'
        f'Quelle: https://github.com/{OWNER}/{repo_name}'
    )
    gh('pr', 'create', '--repo', full_repo, '--head', branch, '--base', 'main',
       '--title', f'Neue Plugin-Kachel: {copy["name"]} (Entwurf, bitte pruefen)', '--body', body)
    print(f'PR geoeffnet fuer {repo_name}')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', type=Path, default=Path('index.html'))
    args = parser.parse_args()
    html_text = args.index.read_text(encoding='utf-8')
    listed = existing_card_repos(html_text)
    opened = 0
    for repo in sorted(repositories(), key=lambda r: r['name'].casefold()):
        name = repo['name']
        if name in listed or name == f'{OWNER}.github.io':
            continue
        try:
            if open_pr_for(name, args.index):
                opened += 1
        except subprocess.CalledProcessError as e:
            print(f'SKIP {name}: {e}', file=sys.stderr)
        subprocess.run(['git', 'checkout', 'main'], check=True)
        subprocess.run(['git', 'reset', '--hard', 'origin/main'], check=True)
    print(f'{opened} neue Entwurfs-PR(s) geoeffnet')


if __name__ == '__main__':
    main()
