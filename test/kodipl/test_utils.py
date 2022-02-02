
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'script.module.kodipl' / 'lib'))

from kodipl import utils  # noqa: E402
import kodipl             # noqa: E402


class E1(Exception):  pass  # noqa: E272, E701


class X1:  pass  # noqa: E272, E701
class X2:  pass  # noqa: E272, E701
class X3:  pass  # noqa: E272, E701
class X4:  pass  # noqa: E272, E701
class X5:  pass  # noqa: E272, E701


class TestADict(TestCase):

    def test_type(self):
        self.assertIsInstance(utils.adict(), dict)

    def test_dict_methods(self):
        for k in dir(dict):
            # I don't know why `fromkeys` are differ
            if k not in {'__class__', '__class_getitem__', '__doc__', '__init_subclass__', '__subclasshook__',
                         'fromkeys'}:
                self.assertIs(getattr(utils.adict, k), getattr(dict, k))

    def test_attr(self):
        self.assertIs(utils.adict((('a', X1),)).a, X1)
        self.assertIsNone(utils.adict((('a', X1),)).b)

    def test_dict(self):
        d = {1: 2, 3: 4}
        self.assertDictEqual(utils.adict(d), d)

    def test_pikle(self):
        self.assertIs(type(utils.adict().__getstate__()), dict)
        with patch('kodipl.utils.dict') as mock_dict:
            x = kodipl.utils.adict()
            x.__getstate__()
            mock_dict.assert_called_once_with(x)


class TestMkMDict(TestCase):

    def test_mkmdict(self):
        self.assertDictEqual(utils.mkmdict(()), {})
        self.assertDictEqual(utils.mkmdict(((1, 2),)), {1: [2]})
        self.assertDictEqual(utils.mkmdict(((1, 2), (1, 3))), {1: [2, 3]})


class TestItemIter(TestCase):

    def test_value(self):
        self.assertTupleEqual(utils.item_iter(None), ())
        self.assertIs(utils.item_iter(X1), X1)

    def test_seq(self):
        d = {1: 2}
        self.assertEqual(utils.item_iter(d), d.items())
        self.assertIs(type(utils.item_iter(d)), type(d.items()))


class TestGetAttr(TestCase):

    def test_empty(self):
        false = MagicMock()
        false.__bool__.return_value = False
        self.assertIsNone(utils.get_attr(X1, None))
        self.assertIsNone(utils.get_attr(X1, false))

    def test_args(self):
        self.assertIs(utils.get_attr(None, None, default=X1), X1)
        with patch('kodipl.utils.getattr', return_value=X1) as mock:
            self.assertIs(utils.get_attr(X1, 'a:b', sep=':'), X1)
            mock.assert_has_calls([
                call(X1, 'a'),
                call(X1, 'b'),
            ])

    def test_obj_name(self):
        with patch('kodipl.utils.getattr', return_value=X3) as mock:
            self.assertIs(utils.get_attr(X1, 'a'), X3)
            mock.assert_called_once_with(X1, 'a')
        with patch('kodipl.utils.getattr', return_value=X3) as mock:
            self.assertIs(utils.get_attr(X1, 'a.b'), X3)
            mock.assert_has_calls([
                call(X1, 'a'),
                call(X3, 'b'),
            ])

    def test_obj_attr(self):
        with patch('kodipl.utils.getattr', return_value=X3) as mock:
            self.assertIs(utils.get_attr(X1, [X2]), X3)
            mock.assert_called_once_with(X1, X2)
        with patch('kodipl.utils.getattr', side_effect=E1) as mock:
            with self.assertRaises(E1):
                utils.get_attr(X1, [X2])
            mock.assert_called_once_with(X1, X2)

    def test_global_attr(self):
        with patch('kodipl.utils.globals', return_value={'a': X3}) as mock:
            self.assertIs(utils.get_attr(None, 'a'), X3)
            mock.assert_called_once_with()
        with patch('kodipl.utils.globals', return_value={'x': X3}) as mock:
            self.assertIs(utils.get_attr(None, 'a', default=X2), X2)
            mock.assert_called_once_with()
        with (patch('kodipl.utils.globals', return_value={'a': X2}) as mock_globals,
              patch('kodipl.utils.getattr', return_value=X3) as mock_getattr):
            self.assertIs(utils.get_attr(None, 'a.b'), X3)
            mock_globals.assert_called_once_with()
            mock_getattr.assert_called_once_with(X2, 'b')


class TestEncodeData(TestCase):

    def test_encode(self):
        mock1, mock2 = MagicMock(), MagicMock()
        mock1.replace.return_value = mock2
        mock2.decode.return_value = X4
        with (patch('kodipl.utils.pickle.dumps', return_value=X2) as mock_dumps,
              patch('kodipl.utils.gzip.compress', return_value=X3) as mock_gzip,
              patch('kodipl.utils.b64encode', return_value=mock1) as mock_b64encode):
            self.assertIs(utils.encode_data(X1), X4)
            mock_dumps.assert_called_once_with(X1)
            mock_gzip.assert_called_once_with(X2)
            mock_b64encode.assert_called_once_with(X3, b'-_')
            mock1.replace.assert_called_once_with(b'=', b'')
            mock2.decode.assert_called_once_with('ascii')


class TestEncodeUrl(TestCase):

    def test_url_incorect(self):
        with self.assertRaises(TypeError):
            utils.encode_url()
        with self.assertRaises(TypeError):
            utils.encode_url(None)

    def test_url_path_none(self):
        self.assertEqual(utils.encode_url('A'), 'A')
        self.assertEqual(utils.encode_url('A', path=None), 'A')

    def test_url_path_abs_1(self):
        self.assertEqual(utils.encode_url('A', path='/B'), 'A/B')
        self.assertEqual(utils.encode_url('//A', path='/B'), '//A/B')
        self.assertEqual(utils.encode_url('X://A', path='/B'), 'X://A/B')

    def test_url_path_abs_2(self):
        self.assertEqual(utils.encode_url('X://A/n', path='/B'), 'X://A/B')

    def test_url_path_rel_1(self):
        self.assertEqual(utils.encode_url('A', path='B'), 'A/B')
        self.assertEqual(utils.encode_url('//A', path='/B'), '//A/B')
        self.assertEqual(utils.encode_url('X://A', path='/B'), 'X://A/B')

    def test_url_path_rel_2(self):
        self.assertEqual(utils.encode_url('X://A/n', path='B'), 'X://A/B')
        self.assertEqual(utils.encode_url('X://A/N/m', path='B'), 'X://A/N/B')

    def test_url_path_rel_3(self):
        self.assertEqual(utils.encode_url('X://A', path='B'), 'X://A/B')
