"""The behaviour lock knows an intended change (M9.7): the M9.3 proof on flaskr added a link to the shared navigation,
and the lock refused it on every screen. A card that declares the screens it changes passes there with only its
declared addition; anything else still fails."""
import json
import subprocess
from pathlib import Path

from shared_fixture import Workspace

from eaos.live.behavior.intended import for_pass, only_added, restore_intended, screens_of
from eaos.live.behavior.lock import spec_statuses

PAGES = {'root': 'Flaskr Register Log In Posts Hello world', 'auth-register': 'Flaskr Register Log In Register Username Password'}
ADDED = {'root': 'Flaskr About Register Log In Posts Hello world', 'auth-register': 'Flaskr About Register Log In Register Username Password'}
NAV = {'id': 'EXT-001', 'changes_screens': {'screens': ['all'], 'adds': ['About']}}


def looks(name, ratio='0.00'):
    return (f'Error: expect(page).toHaveScreenshot(expected) failed\n\n  812 pixels (ratio {ratio} of all image pixels) are '
            f'different.\n\n  Snapshot: {name}.png')


def report(*names, message=looks):
    """Playwright's JSON report of the flaskr lock: one spec per page, each failing with `message`."""
    return {'suites': [{'file': f'{name}.spec.ts', 'specs': [{'title': f'/{name} renders as it does today', 'tests': [
        {'results': [{'status': 'failed', 'error': {'message': message(name)}}]}]}]} for name in names]}


class IntendedChangeTests(Workspace):
    def lock_with(self, received):
        """The lock folder holding the recorded words, and the pass's words folder holding `received`."""
        lock, words = Path(self.tmp) / 'lock', Path(self.tmp) / 'words'
        for folder, texts in ((lock / '__screenshots__', PAGES), (words, received)):
            for name, text in texts.items():
                (folder / f'{name}.spec.ts').mkdir(parents=True, exist_ok=True)
                (folder / f'{name}.spec.ts' / f'{name}.text.txt').write_text(text)
        return lock, words

    def statuses(self, received, cards, message=looks):
        lock, words = self.lock_with(received)
        found = spec_statuses(report(*PAGES, message=message), (), (), for_pass(screens_of(cards), lock, words, None))
        return {file: status for file, (status, _) in found.items()}

    def test_a_nav_link_added_to_every_page_passes_with_the_declaration_and_fails_without_it(self):
        self.assertEqual(self.statuses(ADDED, [NAV]), {'root.spec.ts': 'passed', 'auth-register.spec.ts': 'passed'})
        self.assertEqual(self.statuses(ADDED, [{'id': 'EXT-001'}]), {'root.spec.ts': 'failed', 'auth-register.spec.ts': 'failed'},
                         'a card without the declaration is judged as before')
        words = lambda name: f"Error: expect(string).toMatchSnapshot(expected) failed\n\n  Snapshot: {name}.text.txt"
        self.assertEqual(set(self.statuses(ADDED, [NAV], words).values()), {'passed'}, 'its words differing, the picture alike')

    def test_a_declared_screen_that_also_loses_a_word_or_breaks_its_layout_still_fails(self):
        lost = {**ADDED, 'root': 'Flaskr About Register Posts Hello world'}            # "Log In" gone
        self.assertEqual(self.statuses(lost, [NAV]), {'root.spec.ts': 'failed', 'auth-register.spec.ts': 'passed'})
        other = {**ADDED, 'root': 'Flaskr About Contact Register Log In Posts Hello world'}  # a word nobody declared
        self.assertEqual(self.statuses(other, [NAV])['root.spec.ts'], 'failed')
        self.assertEqual(set(self.statuses(ADDED, [NAV], lambda n: looks(n, '0.40')).values()), {'failed'}, 'a layout broken')
        resized = lambda n: 'Expected an image 1280px by 720px, received 1280px by 900px. ' + looks(n)
        self.assertEqual(set(self.statuses(ADDED, [NAV], resized).values()), {'failed'})
        console = lambda n: f'Error: expect(string).toMatchSnapshot(expected) failed\n  Snapshot: {n}.console.txt'
        self.assertEqual(set(self.statuses(ADDED, [NAV], console).values()), {'failed'}, "a page's errors stay locked")
        only_home = {'id': 'EXT-002', 'changes_screens': {'screens': ['/'], 'adds': ['About']}}
        self.assertEqual(self.statuses(ADDED, [only_home]), {'root.spec.ts': 'passed', 'auth-register.spec.ts': 'failed'},
                         'a screen the card did not declare still fails')
        self.assertFalse(only_added('a b c', 'a c About', {'About'}))
        self.assertTrue(only_added('a b c', 'a About b c', {'about'}))

    def test_the_batch_declares_the_screens_and_a_design_card_with_a_declaration_is_no_longer_free_on_every_screen(self):
        from eaos.journeys.fix.waves.batch import declared_screens, intended_screens
        self.assertEqual(intended_screens([NAV, {'id': 'TASK-1'}]), {'*': frozenset({'About'})})
        design = {'design': {'findings': [{'page': '/'}]}}
        self.assertEqual(declared_screens([design]), {'*'})
        self.assertEqual(declared_screens([{**design, **NAV}]), set())

    def test_the_extend_planner_declares_every_screen_when_the_feature_changes_the_shared_layout(self):
        from eaos.journeys.extend import _card, _feature_fit
        nav = {'id': 'F1', 'name': 'About page', 'paths': ['flaskr/templates/base.html', 'flaskr/about.py']}
        self.assertIn('changes_screens.adds', ' '.join(_feature_fit(nav, None, [], ({'flaskr/templates', 'flaskr'}, {}))))
        card = _card('EXT-001', 'X01', 'About', {**nav, 'changes_screens': {'adds': ['About']}}, False)
        self.assertEqual(card['changes_screens'], {'screens': ['all'], 'adds': ['About']})
        self.assertNotIn('changes_screens', _card('EXT-002', 'X01', 'About', {**nav, 'paths': ['flaskr/about.py']}, False))

    def test_a_kept_intended_change_is_the_new_truth_only_for_code_that_holds_its_commit(self):
        repo, recorded, lock = Path(self.tmp) / 'repo', Path(self.tmp) / 'recorded', Path(self.tmp) / 'lock'
        git = lambda *args: subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()
        repo.mkdir()
        git('init', '-q')
        git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'base')
        base = git('rev-parse', 'HEAD')
        git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'nav link')
        kept = git('rev-parse', 'HEAD')
        (recorded / 'intended' / kept / 'root.spec.ts').mkdir(parents=True)
        (recorded / 'intended' / kept / 'root.spec.ts/root.text.txt').write_text(ADDED['root'])
        (recorded / 'intended/index.json').write_text(json.dumps([{'commit': kept, 'screens': ['root.spec.ts/root.text.txt']}]))
        restore_intended(recorded, lock, repo)
        self.assertEqual((lock / '__screenshots__/root.spec.ts/root.text.txt').read_text(), ADDED['root'])
        (lock / '__screenshots__/root.spec.ts/root.text.txt').unlink()
        git('checkout', '-q', base)
        restore_intended(recorded, lock, repo)
        self.assertFalse((lock / '__screenshots__/root.spec.ts/root.text.txt').exists(), 'code without the change keeps the original')
