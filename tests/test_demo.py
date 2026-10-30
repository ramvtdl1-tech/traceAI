import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from demo_support import RequestBudget, bounded_history, memory_candidates
from database.memory_extractor import extract_memory_candidates

ROOT = Path(__file__).resolve().parents[1]


def response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class LimitsTests(unittest.TestCase):
    def test_history_is_bounded_and_starts_with_user(self):
        messages = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': 'x' * 1000} for i in range(101)]
        result = bounded_history(messages)
        self.assertLessEqual(len(result), 40)
        self.assertLessEqual(sum(len(m['content']) for m in result), 24000)
        self.assertEqual(result[0]['role'], 'user')
        self.assertEqual(result[-1], messages[-1])

    def test_shared_quota_expires(self):
        now = [10.0]
        budget = RequestBudget(limit=2, window_seconds=10, clock=lambda: now[0])
        self.assertTrue(budget.claim())
        self.assertTrue(budget.claim())
        self.assertFalse(budget.claim())
        now[0] = 20.0
        self.assertTrue(budget.claim())

    def test_memories_deduplicate_and_require_approval(self):
        candidates = [
            {'content': 'Likes Python', 'sensitivity': 'normal'},
            {'content': 'Likes Python!', 'sensitivity': 'normal'},
            {'content': 'Sensitive fact', 'sensitivity': 'sensitive'},
        ]
        result = memory_candidates(candidates, [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['status'], 'pending')
        self.assertEqual(memory_candidates(candidates, result), [])

    def test_extractor_rejects_invalid_json_schema_and_confidence(self):
        from unittest.mock import Mock
        client = Mock()
        create = client.chat.completions.create
        for text in ('not json', '{"memories": null}', '[]', '```'):
            create.return_value = response(text)
            with self.assertRaises(ValueError):
                extract_memory_candidates('I like Python', client=client, model='fake')
        create.return_value = response('```json\n' + json.dumps({'memories': [
            {'content': 'Likes Python', 'confidence': True, 'sensitivity': 'normal'}
        ]}) + '\n```')
        result = extract_memory_candidates('I like Python', client=client, model='fake')
        self.assertEqual(result[0]['confidence'], 0.0)


class AppTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            'NEBIUS_API_KEY': 'fake-test-key', 'NEBIUS_MODEL': 'fake-model',
            'NEBIUS_BASE_URL': 'https://example.invalid/v1/', 'DEMO_ACCESS_CODE': '',
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.provider = patch('openai.OpenAI')
        factory = self.provider.start()
        self.addCleanup(self.provider.stop)
        self.create = factory.return_value.__enter__.return_value.chat.completions.create
        self.create.return_value = response('Test answer')

    def app(self):
        app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=20)
        self.assertFalse(app.exception)
        return app

    def click(self, app, label):
        next(b for b in app.button if b.label == label).click().run(timeout=20)
        self.assertFalse(app.exception)

    def chat(self, app, text):
        app.session_state['last_request'] = 0.0
        app.chat_input[0].set_value(text).run(timeout=20)
        self.assertFalse(app.exception)

    def test_two_visitors_and_reset_never_share_or_touch_disk(self):
        paths = [ROOT / 'trace_history.json', ROOT / 'data/trace_memory.db']
        before = {p: p.read_bytes() for p in paths if p.exists()}
        first = self.app()
        self.assertEqual(first.session_state['messages'], [])
        self.assertEqual(first.session_state['memories'], [])
        self.chat(first, 'Only visitor one sees this')
        second = self.app()
        self.assertEqual(second.session_state['messages'], [])
        self.chat(second, 'Only visitor two sees this')
        self.click(first, '＋ New conversation')
        self.assertEqual(first.session_state['messages'], [])
        self.assertEqual(second.session_state['messages'][0]['content'], 'Only visitor two sees this')
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_memory_review_recall_removal_and_isolation(self):
        app = self.app()
        self.chat(app, 'I am learning Python.')
        app.session_state['last_request'] = 0.0
        self.create.return_value = response(json.dumps({'memories': [
            {'content': 'User is learning Python.', 'sensitivity': 'normal', 'confidence': .99},
            {'content': 'Private medical information', 'sensitivity': 'sensitive'},
        ]}))
        self.click(app, 'Find memories')
        self.assertEqual(len(app.session_state['memories']), 1)
        self.assertEqual(app.session_state['memories'][0]['status'], 'pending')
        self.create.return_value = response('A helpful answer')
        self.chat(app, 'What should I learn?')
        self.assertNotIn('User is learning Python.', self.create.call_args.kwargs['messages'][0]['content'])
        self.click(app, 'Approve')
        other = self.app()
        self.assertEqual(other.session_state['memories'], [])
        self.click(app, '＋ New conversation')
        self.chat(app, 'What am I learning?')
        self.assertIn('User is learning Python.', self.create.call_args.kwargs['messages'][0]['content'])
        self.click(app, 'Remove')
        self.assertEqual(app.session_state['memories'], [])
        self.chat(app, 'What do you remember?')
        self.assertNotIn('User is learning Python.', self.create.call_args.kwargs['messages'][0]['content'])

    def test_provider_failures_preserve_chat_and_hide_details(self):
        app = self.app()
        self.chat(app, 'hello')
        before = list(app.session_state['messages'])
        for failure in (RuntimeError('secret-provider-details'), None):
            self.create.side_effect = failure
            self.create.return_value = response('')
            self.chat(app, 'try again')
            self.assertEqual(app.session_state['messages'], before)
            self.assertTrue(app.error)
            self.assertFalse(app.code)
            self.assertNotIn('secret-provider-details', str(app.error))

    def test_session_limits_and_missing_config(self):
        app = self.app()
        app.session_state['request_count'] = 40
        self.chat(app, 'over quota')
        self.create.assert_not_called()
        self.assertTrue(app.warning)
        os.environ['NEBIUS_API_KEY'] = ''
        missing = self.app()
        self.assertFalse(missing.chat_input)

    def test_access_code_gates_chat(self):
        os.environ['DEMO_ACCESS_CODE'] = 'judges-only'
        app = self.app()
        self.assertFalse(app.chat_input)
        app.text_input[0].set_value('wrong')
        self.click(app, 'Open demo')
        self.assertTrue(app.error)
        self.assertFalse(app.chat_input)
        app.text_input[0].set_value('judges-only')
        self.click(app, 'Open demo')
        self.assertTrue(app.chat_input)
        self.create.assert_not_called()

    def test_outgoing_context_bounds(self):
        app = self.app()
        app.session_state['messages'] = [
            {'role': 'user' if i % 2 == 0 else 'assistant', 'content': 'x' * 1000}
            for i in range(100)
        ]
        self.chat(app, 'last prompt')
        sent = self.create.call_args.kwargs['messages'][1:]
        self.assertLessEqual(len(sent), 40)
        self.assertLessEqual(sum(len(m['content']) for m in sent), 24000)
        self.assertEqual(sent[-1]['content'], 'last prompt')


if __name__ == '__main__':
    unittest.main()
