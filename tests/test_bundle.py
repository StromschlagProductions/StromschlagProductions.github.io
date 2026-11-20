import base64
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('bundle', Path(__file__).parents[1] / 'scripts/build_bundle.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def archive(product='Voice', version='1.0', extra=None, vendor=b.VENDOR, machine=0x8664):
    pe = bytearray(128)
    pe[:2] = b'MZ'
    struct.pack_into('<I', pe, 0x3c, 64)
    pe[64:68] = b'PE\0\0'
    struct.pack_into('<H', pe, 68, machine)
    cid = b.sha(product.encode())[:32].upper()
    metadata = dict(Name=product, Version=version, **{'Factory Info': {'Vendor': vendor},
        'Classes': [{'Category': 'Audio Module Class', 'Vendor': vendor, 'CID': cid}]})
    files = {f'{product}.vst3/Contents/x86_64-win/{product}.vst3': bytes(pe),
             f'{product}.vst3/Contents/Resources/moduleinfo.json': json.dumps(metadata).encode()}
    files.update(extra or {})
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        for n, data in files.items():
            z.writestr(n, data)
    return out.getvalue()


def candidate(product='Voice', data=None, asset_id=1):
    data = data if data is not None else archive(product)
    return dict(repository=product+'-vst', product=product, version='v1.0', release_id=1,
                asset_id=asset_id, asset_name=product+'-v1.0-Windows-VST3.zip', asset_size=len(data),
                asset_updated_at='2026-11-19T00:00:00Z', digest='sha256:'+b.sha(data),
                url=f'https://github.com/{b.OWNER}/{product}-vst/releases/download/v1.0/{product}.zip')


class BundleTests(unittest.TestCase):
    def test_valid_module_and_legal_notices(self):
        data = archive(extra={'THIRD_PARTY_NOTICES.md': b'license', 'tests.txt': b'no'})
        files, cids = b.validate_zip(data, 'Voice', 'v1.0.0')
        self.assertIn('LIZENZEN/Voice/THIRD_PARTY_NOTICES.md', files)
        self.assertNotIn('tests.txt', files)
        self.assertEqual(len(cids), 1)

    def test_moduleinfo_trailing_commas_preserves_strings(self):
        self.assertEqual(b.relaxed_json('{"x":",}","y":[1,],}'), {'x': ',}', 'y': [1]})

    def test_path_attacks(self):
        for name in ['../evil', '/evil', 'x/../../evil', 'x\\evil', 'C:/evil', 'x/CON.txt', 'x/a.']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                b.validate_zip(archive(extra={name: b'bad'}), 'Voice', '1.0')

    def test_identity_architecture_and_missing_module(self):
        for data in [archive(vendor='Other'), archive(machine=0x14c), archive(product='Wrong')]:
            with self.assertRaises(ValueError):
                b.validate_zip(data, 'Voice', '1.0')
        with self.assertRaises(ValueError):
            b.validate_zip(archive(), 'Voice', '2.0')
        with self.assertRaises(zipfile.BadZipFile):
            b.validate_zip(b'not zip', 'Voice', '1.0')

    def test_duplicate_and_symlink(self):
        for mode in ['duplicate', 'symlink']:
            out = io.BytesIO(archive())
            with zipfile.ZipFile(out, 'a') as z:
                if mode == 'duplicate':
                    z.writestr('Voice.vst3/Contents/Resources/moduleinfo.json', b'{}')
                else:
                    i = zipfile.ZipInfo('Voice.vst3/link')
                    i.create_system = 3
                    i.external_attr = 0o120777 << 16
                    z.writestr(i, '../escape')
            with self.assertRaises(ValueError):
                b.validate_zip(out.getvalue(), 'Voice', '1.0')

    def test_new_repo_discovered_without_name_convention(self):
        release = dict(draft=False, prerelease=False, published_at='now', tag_name='v1.0', id=3,
                       assets=[dict(id=1, state='uploaded', name='Voice-Windows-VST3.zip', size=10,
                                    updated_at='now', browser_download_url=f'https://github.com/{b.OWNER}/unexpected/releases/download/v1.0/Voice.zip')])
        cmake = base64.b64encode(b'juce_add_plugin(Voice COMPANY_NAME "Stromschlag Audio" FORMATS VST3)').decode()
        def api(path):
            return dict(content=cmake, type='file') if '/contents/' in path else release
        with patch.object(b, 'repositories', return_value=[{'name': 'unexpected'}]), patch.object(b, 'api', side_effect=api):
            found, _ = b.snapshot(Path('.'))
        self.assertEqual(found[0]['repository'], 'unexpected')

    def test_stable_release_and_unique_asset(self):
        release = dict(draft=False, prerelease=True, published_at='now', assets=[])
        with self.assertRaises(ValueError):
            b.choose_asset(release, 'Voice')
        release.update(prerelease=False, _repository='Voice-vst')
        with self.assertRaises(ValueError):
            b.choose_asset(release, 'Voice')

    def test_build_noop_new_plugin_and_root_structure(self):
        data = archive()
        rows = [candidate(data=data)]
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'snapshot', side_effect=lambda *_: (list(rows), [])), patch.object(b, 'download', side_effect=lambda url: archive('Other') if 'Other-vst' in url else data):
            out = Path(tmp)
            first = b.build(out)
            before = (out/b.ARCHIVE).read_bytes()
            self.assertIsNone(b.build(out, first))
            self.assertEqual((out/b.ARCHIVE).read_bytes(), before)
            rows.append(candidate('Other', asset_id=2))
            second = b.build(out, first)
            self.assertEqual(len(second['plugins']), 2)
            with zipfile.ZipFile(out/b.ARCHIVE) as z:
                roots = {n.split('/')[0] for n in z.namelist()}
                self.assertEqual(roots, {'Voice.vst3', 'Other.vst3', 'VERSIONEN.txt', 'INSTALLATION.txt'})

    def test_bad_new_candidate_skipped_existing_failure_preserves_zip(self):
        data = archive()
        rows = [candidate(data=data)]
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'snapshot', side_effect=lambda *_: (list(rows), [])), patch.object(b, 'download', return_value=data):
            out = Path(tmp)
            first = b.build(out)
            before = (out/b.ARCHIVE).read_bytes()
            rows.append(candidate('Wrong', data=b'bad', asset_id=2))
            # mismatch and bad ZIP are rejected; unchanged valid bundle is not republished
            self.assertIsNone(b.build(out, first))
            self.assertEqual((out/b.ARCHIVE).read_bytes(), before)
            rows[0] = dict(rows[0], digest='sha256:bad')
            with self.assertRaises(ValueError):
                b.build(out, first)
            self.assertEqual((out/b.ARCHIVE).read_bytes(), before)

    def test_disappeared_known_plugin_blocks_update(self):
        with patch.object(b, 'repositories', return_value=[]), self.assertRaises(ValueError):
            b.snapshot(Path('.'), {'plugins': [{'repository': 'Voice-vst'}]})

    def test_publication_failure_never_promotes_draft(self):
        calls = []
        def gh(cmd, **kwargs):
            calls.append(cmd)
            if 'upload' in cmd:
                raise RuntimeError('network failure')
            return ''
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'api', return_value=None), patch.object(b.subprocess, 'check_output', side_effect=gh), patch.dict('os.environ', GITHUB_SHA='a'*40):
            with self.assertRaises(RuntimeError):
                b.publish(Path(tmp), {'fingerprint': 'a'*64, 'plugins': []}, 'owner/repo')
        self.assertTrue(any('create' in c and '--draft' in c for c in calls))
        self.assertFalse(any('edit' in c for c in calls))


class PluginProductTests(unittest.TestCase):
    def test_product_name_overrides_target_name(self):
        text = 'juce_add_plugin(Moves\n    COMPANY_NAME "Stromschlag Audio"\n    PRODUCT_NAME "MOVES"\n    IS_SYNTH FALSE)\njuce_add_console_app(T PRODUCT_NAME "Other")\n'
        self.assertEqual(b.plugin_product(text), 'MOVES')

    def test_falls_back_to_target_name(self):
        text = 'juce_add_plugin(Voice\n    COMPANY_NAME "Stromschlag Audio")\njuce_add_console_app(T PRODUCT_NAME "Other")\n'
        self.assertEqual(b.plugin_product(text), 'Voice')


if __name__ == '__main__':
    unittest.main()
