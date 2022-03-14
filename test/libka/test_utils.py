
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'script.module.libka' / 'lib'))

from libka import utils  # noqa: E402
import libka             # noqa: E402


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
        with patch('libka.utils.dict') as mock_dict:
            x = libka.utils.adict()
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
        with patch('libka.utils.getattr', return_value=X1) as mock:
            self.assertIs(utils.get_attr(X1, 'a:b', sep=':'), X1)
            mock.assert_has_calls([
                call(X1, 'a'),
                call(X1, 'b'),
            ])

    def test_obj_name(self):
        with patch('libka.utils.getattr', return_value=X3) as mock:
            self.assertIs(utils.get_attr(X1, 'a'), X3)
            mock.assert_called_once_with(X1, 'a')
        with patch('libka.utils.getattr', return_value=X3) as mock:
            self.assertIs(utils.get_attr(X1, 'a.b'), X3)
            mock.assert_has_calls([
                call(X1, 'a'),
                call(X3, 'b'),
            ])

    def test_obj_attr(self):
        with patch('libka.utils.getattr', return_value=X3) as mock:
            self.assertIs(utils.get_attr(X1, [X2]), X3)
            mock.assert_called_once_with(X1, X2)
        with patch('libka.utils.getattr', side_effect=E1) as mock:
            with self.assertRaises(E1):
                utils.get_attr(X1, [X2])
            mock.assert_called_once_with(X1, X2)
        with patch('libka.utils.getattr', side_effect=AttributeError) as mock:
            self.assertIs(utils.get_attr(X1, [X2], default=X3), X3)
            mock.assert_called_once_with(X1, X2)

    def test_global_attr(self):
        with patch('libka.utils.globals', return_value={'a': X3}) as mock:
            self.assertIs(utils.get_attr(None, 'a'), X3)
            mock.assert_called_once_with()
        with patch('libka.utils.globals', return_value={'x': X3}) as mock:
            self.assertIs(utils.get_attr(None, 'a', default=X2), X2)
            mock.assert_called_once_with()
        with (patch('libka.utils.globals', return_value={'a': X2}) as mock_globals,
              patch('libka.utils.getattr', return_value=X3) as mock_getattr):
            self.assertIs(utils.get_attr(None, 'a.b'), X3)
            mock_globals.assert_called_once_with()
            mock_getattr.assert_called_once_with(X2, 'b')


class TestEncodeData(TestCase):

    def test_encode(self):
        mock1, mock2 = MagicMock(), MagicMock()
        mock1.replace.return_value = mock2
        mock2.decode.return_value = X4
        with (patch('libka.utils.pickle.dumps', return_value=X2) as mock_dumps,
              patch('libka.utils.gzip.compress', return_value=X3) as mock_gzip,
              patch('libka.utils.b64encode', return_value=mock1) as mock_b64):
            self.assertIs(utils.encode_data(X1), X4)
            mock_dumps.assert_called_once_with(X1)
            mock_gzip.assert_called_once_with(X2)
            mock_b64.assert_called_once_with(X3, b'-_')
            mock1.replace.assert_called_once_with(b'=', b'')
            mock2.decode.assert_called_once_with('ascii')


class TestDecodeData(TestCase):

    def test_decode(self):
        with (patch('libka.utils.b64decode', return_value=X2) as mock_b64,
              patch('libka.utils.gzip.decompress', return_value=X3) as mock_gzip,
              patch('libka.utils.pickle.loads', return_value=X4) as mock_dumps):
            self.assertIs(utils.decode_data(b'abcd'), X4)
            mock_b64.assert_called_once_with(b'abcd', b'-_')
            mock_gzip.assert_called_once_with(X2)
            mock_dumps.assert_called_once_with(X3)

    def test_encode(self):
        mock1, mock2 = MagicMock(), MagicMock()
        mock1.encode.return_value = mock2
        mock2.__len__.return_value = 1
        mock2.__iadd__.return_value = mock2
        with (patch('libka.utils.b64decode', return_value=X2) as mock_b64,
              patch('libka.utils.gzip.decompress', return_value=X3) as mock_gzip,
              patch('libka.utils.pickle.loads', return_value=X4) as mock_dumps):
            self.assertIs(utils.decode_data(mock1), X4)
            mock1.encode.assert_called_once_with('utf8')
            mock2.__len__.assert_called_once_with()
            mock2.__iadd__.assert_called_once_with(b'===')
            mock_b64.assert_called_once_with(mock2, b'-_')
            mock_gzip.assert_called_once_with(X2)
            mock_dumps.assert_called_once_with(X3)


class TestParseUrl(TestCase):

    def test_raw(self):
        with patch('libka.utils.decode_data', return_value='ou') as mock:
            self.assertEqual(utils.parse_url('//a/b?c=42', raw={'c'}),
                             utils.ParsedUrl('//a/b?c=42', '', '', 'a', None, '/b', {'c': ['ou']}, ''))
            mock.assert_called_once_with('42')

    def test_host(self):
        self.assertEqual(utils.parse_url('/a').host, '')
        self.assertEqual(utils.parse_url('/a/b').host, '')
        self.assertEqual(utils.parse_url('x:a').host, '')
        self.assertEqual(utils.parse_url('x:/a/b').host, '')
        self.assertEqual(utils.parse_url('//a').host, 'a')
        self.assertEqual(utils.parse_url('//a/b').host, 'a')
        self.assertEqual(utils.parse_url('x://a').host, 'a')
        self.assertEqual(utils.parse_url('x://a/b').host, 'a')

        self.assertIsNone(utils.parse_url('/a').port)
        self.assertIsNone(utils.parse_url('/a/b').port)
        self.assertIsNone(utils.parse_url('x:a').port)
        self.assertIsNone(utils.parse_url('x:/a/b').port)
        self.assertIsNone(utils.parse_url('//a').port)
        self.assertIsNone(utils.parse_url('//a/b').port)
        self.assertIsNone(utils.parse_url('x://a').port)
        self.assertIsNone(utils.parse_url('x://a/b').port)

        self.assertEqual(utils.parse_url('//a:1').port, 1)
        self.assertEqual(utils.parse_url('//a:1/b').port, 1)
        self.assertEqual(utils.parse_url('x://a:1').port, 1)
        self.assertEqual(utils.parse_url('x://a:1/b').port, 1)

        self.assertEqual(utils.parse_url('x://a/b').authority, 'a')
        self.assertEqual(utils.parse_url('x://a:1/b').authority, 'a:1')
        self.assertEqual(utils.parse_url('x://u@a:1/b').authority, 'u@a:1')
        self.assertEqual(utils.parse_url('x://u:p@a:1/b').authority, 'u:p@a:1')

        self.assertIsNone(utils.parse_url('x://a:/b').port)
        self.assertIsNone(utils.parse_url('x://a:0/b').port)
        with self.assertRaises(ValueError):
            utils.parse_url('x://a:z/b')
        with self.assertRaises(ValueError):
            utils.parse_url('x://a:65536/b')

    def test_user(self):
        self.assertEqual(utils.parse_url('//a').user, '')
        self.assertEqual(utils.parse_url('//a/b').user, '')
        self.assertEqual(utils.parse_url('x://a').user, '')
        self.assertEqual(utils.parse_url('x://a/b').user, '')
        self.assertEqual(utils.parse_url('//u@a').user, 'u')
        self.assertEqual(utils.parse_url('//u@a/b').user, 'u')
        self.assertEqual(utils.parse_url('x://u@a').user, 'u')
        self.assertEqual(utils.parse_url('x://u@a/b').user, 'u')
        self.assertEqual(utils.parse_url('//u:p@a').user, 'u')
        self.assertEqual(utils.parse_url('//u:p@a/b').user, 'u')
        self.assertEqual(utils.parse_url('x://u:p@a').user, 'u')
        self.assertEqual(utils.parse_url('x://u:p@a/b').user, 'u')
        self.assertEqual(utils.parse_url('//u:@a/b').user, 'u')
        self.assertEqual(utils.parse_url('x://u:@a/b').user, 'u')

        self.assertEqual(utils.parse_url('//u@a').password, '')
        self.assertEqual(utils.parse_url('//u@a/b').password, '')
        self.assertEqual(utils.parse_url('x://u@a').password, '')
        self.assertEqual(utils.parse_url('x://u@a/b').password, '')
        self.assertEqual(utils.parse_url('//u:p@a').password, 'p')
        self.assertEqual(utils.parse_url('//u:p@a/b').password, 'p')
        self.assertEqual(utils.parse_url('x://u:p@a').password, 'p')
        self.assertEqual(utils.parse_url('x://u:p@a/b').password, 'p')
        self.assertEqual(utils.parse_url('//u:@a/b').password, '')
        self.assertEqual(utils.parse_url('x://u:@a/b').password, '')

        self.assertEqual(utils.parse_url('//u@a/b').credentials, 'u')
        self.assertEqual(utils.parse_url('x://u@a/b').credentials, 'u')
        self.assertEqual(utils.parse_url('//u:@a/b').credentials, 'u:')
        self.assertEqual(utils.parse_url('x://u:@a/b').credentials, 'u:')
        self.assertEqual(utils.parse_url('//u:p@a/b').credentials, 'u:p')
        self.assertEqual(utils.parse_url('x://u:p@a/b').credentials, 'u:p')

    def test_functional(self):
        def test(url, *args):
            self.assertEqual(utils.parse_url(url), utils.ParsedUrl(url, *args))

        #               scheme  cred host port  path  query   fragment
        test(None,          '',  '', '',  None, '',   {}, '')
        test('',            '',  '', '',  None, '',   {}, '')
        test('/a',          '',  '', '',  None, '/a', {}, '')
        test('a',           '',  '', '',  None, 'a',  {}, '')
        test('a://',        'a', '', '',  None, '',   {}, '')
        test('//a',         '',  '', 'a', None, '/',  {}, '')
        test('//a#b',       '',  '', 'a', None, '/',  {}, 'b')
        test('//a?b=2',     '',  '', 'a', None, '/',  {'b': ['2']}, '')
        test('//a?b=2#c',   '',  '', 'a', None, '/',  {'b': ['2']}, 'c')
        test('//a?b=2&c=3', '',  '', 'a', None, '/',  {'b': ['2'], 'c': ['3']}, '')
        test('//a?b=2&b=3', '',  '', 'a', None, '/',  {'b': ['2', '3']}, '')
        test('a:b',         'a', '', '',  None, 'b',  {}, '')


class TestBuildParsedUrlStr(TestCase):

    def test_1(self):
        self.assertEqual(utils.build_parsed_url_str(utils.parse_url('a')), 'a')
        self.assertEqual(utils.build_parsed_url_str(utils.parse_url('a:')), 'a:')
        self.assertEqual(utils.build_parsed_url_str(utils.parse_url('#a')), '#a')
        with patch('libka.utils.encode_params', side_effect=lambda seq: '&'.join(f'{k}={v}' for k, v in seq)) as mock:
            self.assertEqual(utils.build_parsed_url_str(utils.parse_url('//a?x=1&y=2')), '//a/?x=1&y=2')
            mock.assert_called_once()


class TestEncodeParams(TestCase):

    def test_raw(self):
        with patch('libka.utils.encode_data', return_value='xy') as mock:
            self.assertEqual(utils.encode_params(raw={'a': 'b'}), 'a=xy')
            mock.assert_called_once_with('b')

    def test_functional(self):
        self.assertEqual(utils.encode_params(), '')
        self.assertEqual(utils.encode_params({'a': 42, 'b': 'z'}), 'a=42&b=z')


class TestEncodeUrl(TestCase):

    def test_url_incorect(self):
        with self.assertRaises(TypeError):
            utils.encode_url()
        with self.assertRaises(TypeError):
            utils.encode_url(None)

    def test_str_path_none(self):
        self.assertEqual(utils.encode_url('A'), 'A')
        self.assertEqual(utils.encode_url('A', path=None), 'A')

    def test_str_incorrect(self):
        with self.assertRaises(ValueError):
            utils.encode_url('//a:z/', path='/')

    def test_str_path_abs_1(self):
        self.assertEqual(utils.encode_url('A', path='/B'), '/B')
        self.assertEqual(utils.encode_url('//A', path='/B'), '//A/B')
        self.assertEqual(utils.encode_url('X://A', path='/B'), 'X://A/B')

    def test_str_path_abs_2(self):
        self.assertEqual(utils.encode_url('X://A/n', path='/B'), 'X://A/B')

    def test_str_path_rel_1(self):
        self.assertEqual(utils.encode_url('A', path='B'), '/B')
        self.assertEqual(utils.encode_url('//A', path='B'), '//A/B')
        self.assertEqual(utils.encode_url('X://A', path='B'), 'X://A/B')

    def test_str_path_rel_2(self):
        self.assertEqual(utils.encode_url('X://A/n', path='B'), 'X://A/B')
        self.assertEqual(utils.encode_url('X://A/N/m', path='B'), 'X://A/N/B')

    def test_str_path_rel_3(self):
        self.assertEqual(utils.encode_url('X://A', path='B'), 'X://A/B')

    def test_str_path_params(self):
        self.assertEqual(utils.encode_url('//A/N', path='/B', params={'X': 1}), '//A/B?X=1')
        self.assertEqual(utils.encode_url('//A/N?Y=2', path='/B', params={'X': 1}), '//A/B?X=1')
        self.assertEqual(utils.encode_url('//A/N?Y=2', params={'X': 1}), '//A/N?Y=2&X=1')

    def test_str_path_raw(self):
        with patch('libka.utils.encode_data', return_value='ou') as mock:
            self.assertEqual(utils.encode_url('//A/N', path='/B', raw={'X': 1}), '//A/B?X=ou')
            mock.assert_called_once_with(1)
        with patch('libka.utils.encode_data', return_value='ou') as mock:
            self.assertEqual(utils.encode_url('//A/N?Y=2', path='/B', raw={'X': 1}), '//A/B?X=ou')
            mock.assert_called_once_with(1)
        with patch('libka.utils.encode_data', return_value='ou') as mock:
            self.assertEqual(utils.encode_url('//A/N?Y=2', raw={'X': 1}), '//A/N?Y=2&X=ou')
            mock.assert_called_once_with(1)

    def test_url_path_none(self):
        self.assertEqual(utils.encode_url(utils.parse_url('A')),
                         utils.ParsedUrl('A', '', '', '', None, 'A', {}, ''))
        self.assertEqual(utils.encode_url(utils.parse_url('A'), path=None),
                         utils.ParsedUrl('A', '', '', '', None, 'A', {}, ''))

    def test_url_path_abs(self):
        self.assertEqual(utils.encode_url(utils.parse_url('A'), path='/B'),
                         utils.ParsedUrl('/B', '', '', '', None, '/B', {}, ''))
        self.assertEqual(utils.encode_url(utils.parse_url('//A/N/m'), path='/B'),
                         utils.ParsedUrl('//A/B', '', '', 'A', None, '/B', {}, ''))

    def test_url_path_rel(self):
        self.assertEqual(utils.encode_url(utils.parse_url('A'), path='B'),
                         utils.ParsedUrl('/B', '', '', '', None, '/B', {}, ''))
        self.assertEqual(utils.encode_url(utils.parse_url('//A/N/m'), path='B'),
                         utils.ParsedUrl('//A/N/B', '', '', 'A', None, '/N/B', {}, ''))

    def test_url_path_params(self):
        self.assertEqual(utils.encode_url(utils.parse_url('//A/N'), path='/B', params={'X': 1}),
                         utils.ParsedUrl('//A/B?X=1', '', '', 'A', None, '/B', {'X': ['1']}, ''))
        self.assertEqual(utils.encode_url(utils.parse_url('//A/N?Y=2'), path='/B', params={'X': 1}),
                         utils.ParsedUrl('//A/B?X=1', '', '', 'A', None, '/B', {'X': ['1']}, ''))
        self.assertEqual(utils.encode_url(utils.parse_url('//A/N?Y=2'), params={'X': 1}),
                         utils.ParsedUrl('//A/N?Y=2&X=1', '', '', 'A', None, '/N', {'Y': ['2'], 'X': ['1']}, ''))

    def test_url_path_raw(self):
        with patch('libka.utils.encode_data', return_value='ou') as mock:
            self.assertEqual(utils.encode_url(utils.parse_url('//A/N'), path='/B', raw={'X': 1}),
                             utils.ParsedUrl('//A/B?X=ou', '', '', 'A', None, '/B', {'X': ['ou']}, ''))
            mock.assert_called_once_with(1)
        with patch('libka.utils.encode_data', return_value='ou') as mock:
            self.assertEqual(utils.encode_url(utils.parse_url('//A/N?Y=2'), path='/B', raw={'X': 1}),
                             utils.ParsedUrl('//A/B?X=ou', '', '', 'A', None, '/B', {'X': ['ou']}, ''))
            mock.assert_called_once_with(1)
        with patch('libka.utils.encode_data', return_value='ou') as mock:
            self.assertEqual(utils.encode_url(utils.parse_url('//A/N?Y=2'), raw={'X': 1}),
                             utils.ParsedUrl('//A/N?Y=2&X=ou', '', '', 'A', None, '/N', {'Y': ['2'], 'X': ['ou']}, ''))
            mock.assert_called_once_with(1)


class TestSetDefaultX(TestCase):

    def test_empty(self):
        d = {}
        self.assertIs(utils.setdefaultx(d, 'a', None, 42), d)
        self.assertDictEqual(d, {'a': 42})

    def test_exists(self):
        d = {'a': 1}
        self.assertIs(utils.setdefaultx(d, 'a', None, 42), d)
        self.assertDictEqual(d, {'a': 1})

    def test_none(self):
        d = {}
        self.assertIs(utils.setdefaultx(d, 'a', None, None), d)
        self.assertDictEqual(d, {})
