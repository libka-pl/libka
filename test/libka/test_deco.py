
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'script.module.libka' / 'lib'))

from libka import deco  # noqa: E402
import libka            # noqa: E402


class E1(Exception):  pass  # noqa: E272, E701
class E2(Exception):  pass  # noqa: E272, E701


class X1:  pass  # noqa: E272, E701
class X2:  pass  # noqa: E272, E701


class TestRepeatCall(TestCase):

    def test_args(self):
        def fn(): pass
        self.assertTrue(callable(deco.repeat_call()))
        self.assertTrue(callable(deco.repeat_call()(fn)))

    def test_direct(self):
        def fn(): pass
        self.assertTrue(callable(deco.repeat_call(fn)))

    def test_wrap(self):
        def fn(): pass
        fn.__doc__ = doc = """Test DESCR"""
        self.assertEqual(deco.repeat_call(fn).__name__, fn.__name__)
        self.assertEqual(deco.repeat_call(fn).__doc__, doc)

    def test_tries(self):
        mock = MagicMock()
        deco.repeat_call()(mock)()
        self.assertEqual(mock.call_count, 1)
        mock = MagicMock(side_effect=Exception)
        deco.repeat_call()(mock)()
        self.assertEqual(mock.call_count, 3)
        mock = MagicMock(side_effect=Exception)
        deco.repeat_call(tries=5)(mock)()
        self.assertEqual(mock.call_count, 5)
        mock = MagicMock(side_effect=Exception)
        deco.repeat_call(5)(mock)()
        self.assertEqual(mock.call_count, 5)

    def test_delay(self):
        def fn(): raise Exception()
        with patch('libka.deco.xbmc.sleep') as mock:
            deco.repeat_call(tries=1, delay=1)(fn)()
            mock.assert_not_called()
        with patch('libka.deco.xbmc.sleep') as mock:
            deco.repeat_call(tries=2, delay=1)(fn)()
            mock.assert_called_once_with(1000)
        with patch('libka.deco.xbmc.sleep') as mock:
            deco.repeat_call(tries=3, delay=1)(fn)()
            mock.assert_has_calls([call(1000), call(1000)])

    def test_catch(self):
        def fn(): raise E1()
        deco.repeat_call(catch=E1)(fn)()
        with self.assertRaises(E1):
            deco.repeat_call(catch=E2)(fn)()

    def test_onfail(self):
        def fn(a, b=0): raise Exception()
        with (patch('libka.deco.do_call') as call_mock,
              patch('libka.deco.CallDescr', return_value=X2) as descr_mock):
            fail_mock = MagicMock()
            deco.repeat_call(tries=1, on_fail=fail_mock)(fn)(1, b=2)
            descr_mock.assert_called_once_with(fn, (1,), {'b': 2})
            call_mock.assert_called_once_with(fail_mock, ref=X2)
            fail_mock.assert_not_called()
