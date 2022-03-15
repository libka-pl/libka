
import sys
from pathlib import Path
from unittest import TestCase, skip
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'script.module.libka' / 'lib' / '3rd'))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'script.module.libka' / 'lib'))

from libka import utils  # noqa: E402
import libka             # noqa: E402
from libka.url import URL  # noqa: E402
from multidict import MultiDict


class E1(Exception):  pass  # noqa: E272, E701


class X1:  pass  # noqa: E272, E701
class X2:  pass  # noqa: E272, E701
class X3:  pass  # noqa: E272, E701
class X4:  pass  # noqa: E272, E701
class X5:  pass  # noqa: E272, E701


# Hack. Add "x://" to urllib.parse
from urllib.parse import uses_relative, uses_netloc  # noqa: E402
uses_relative.append('x')
uses_netloc.append('x')


class TestParseUrl(TestCase):

    def test_raw(self):
        with patch('libka.utils.decode_data', return_value='ou') as mock:
            self.assertEqual(utils.parse_url('//a/b?c=42', raw={'c'}),
                             URL.build(host='a', path='/b', query={'c': 42}))
            mock.assert_called_once_with('42')
        with patch('libka.utils.decode_data', return_value='ou') as mock:
            self.assertEqual(utils.parse_url('//a/b?c=42', raw={'c'}).query, {'c': 'ou'})
            mock.assert_called_once_with('42')

    def test_host(self):
        self.assertIsNone(utils.parse_url('/a').host)
        self.assertIsNone(utils.parse_url('/a/b').host)
        self.assertIsNone(utils.parse_url('x:a').host)
        self.assertIsNone(utils.parse_url('x:/a/b').host)
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
        self.assertIsNone(utils.parse_url('//a').user)
        self.assertIsNone(utils.parse_url('//a/b').user)
        self.assertIsNone(utils.parse_url('x://a').user)
        self.assertIsNone(utils.parse_url('x://a/b').user)
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

        self.assertIsNone(utils.parse_url('//u@a').password)
        self.assertIsNone(utils.parse_url('//u@a/b').password)
        self.assertIsNone(utils.parse_url('x://u@a').password)
        self.assertIsNone(utils.parse_url('x://u@a/b').password)
        self.assertEqual(utils.parse_url('//u:p@a').password, 'p')
        self.assertEqual(utils.parse_url('//u:p@a/b').password, 'p')
        self.assertEqual(utils.parse_url('x://u:p@a').password, 'p')
        self.assertEqual(utils.parse_url('x://u:p@a/b').password, 'p')
        self.assertEqual(utils.parse_url('//u:@a/b').password, '')
        self.assertEqual(utils.parse_url('x://u:@a/b').password, '')

    def test_functional(self):
        def test(url, scheme, user, password, host, port, path, query, fragment):
            self.assertEqual(utils.parse_url(url),
                             URL.build(scheme=scheme, user=user, password=password, host=host, port=port, path=path,
                                       query=query, fragment=fragment))

        #                scheme  user  pass host port  path  query   fragment
        # test(None,          '',  '',  '', '',  None, '',   {}, '')
        test('',            '',  None, None, '',  None, '',   {}, '')
        test('/a',          '',  None, None, '',  None, '/a', {}, '')
        test('a',           '',  None, None, '',  None, 'a',  {}, '')
        test('a://',        'a', None, None, '',  None, '',   {}, '')
        test('//a',         '',  None, None, 'a', None, '/',  {}, '')
        test('//a#b',       '',  None, None, 'a', None, '/',  {}, 'b')
        test('//a?b=2',     '',  None, None, 'a', None, '/',  MultiDict([('b', '2')]), '')
        test('//a?b=2#c',   '',  None, None, 'a', None, '/',  MultiDict([('b', '2')]), 'c')
        test('//a?b=2&c=3', '',  None, None, 'a', None, '/',  MultiDict([('b', '2'), ('c', '3')]), '')
        test('//a?b=2&b=3', '',  None, None, 'a', None, '/',  MultiDict([('b', '2'), ('b', '3')]), '')
        test('a:b',         'a', None, None, '',  None, 'b',  {}, '')


class TestEncodeParams(TestCase):

    def test_raw(self):
        with patch('libka.utils.encode_data', return_value='xy') as mock:
            self.assertEqual(utils.encode_params(raw={'a': 'b'}), 'a=xy')
            mock.assert_called_once_with('b')

    def test_functional(self):
        self.assertEqual(utils.encode_params(), '')
        self.assertEqual(utils.encode_params({'a': 42, 'b': 'z'}), 'a=42&b=z')

    def test_bool(self):
        # TODO: analyse it, I'm not sure that bool should be supported
        self.assertEqual(utils.encode_params({'a': True, 'b': False}), 'a=true&b=false')


class TestEncodeUrl(TestCase):

    def test_url_incorect(self):
        with self.assertRaises(TypeError):
            utils.encode_url()
        with self.assertRaises(TypeError):
            utils.encode_url(None)

    def test_str_path_none(self):
        self.assertEqual(utils.encode_url('A'), URL('A'))
        self.assertEqual(utils.encode_url('A', path=None), URL('A'))

    def test_str_incorrect(self):
        with self.assertRaises(ValueError):
            utils.encode_url('//a:z/', path='/')

    def test_str_path_abs_1(self):
        self.assertEqual(utils.encode_url('A', path='/B'), URL('/B'))
        self.assertEqual(utils.encode_url('//A', path='/B'), URL('//A/B'))
        self.assertEqual(utils.encode_url('X://A', path='/B'), URL('X://A/B'))

    def test_str_path_abs_2(self):
        self.assertEqual(utils.encode_url('X://A/n', path='/B'), URL('X://A/B'))

    def test_str_path_rel_1(self):
        self.assertEqual(utils.encode_url('A', path='B'), URL('B'))
        self.assertEqual(utils.encode_url('//A', path='B'), URL('//A/B'))
        self.assertEqual(utils.encode_url('X://A', path='B'), URL('X://A/B'))

    def test_str_path_rel_2(self):
        self.assertEqual(utils.encode_url('X://A/n', path='B'), URL('X://A/B'))
        self.assertEqual(utils.encode_url('X://A/N/m', path='B'), URL('X://A/N/B'))

    def test_str_path_rel_3(self):
        self.assertEqual(utils.encode_url('X://A', path='B'), URL('X://A/B'))

    def test_str_path_params(self):
        self.assertEqual(utils.encode_url('//A/N', path='/B', params={'X': 1}), URL('//A/B?X=1'))
        self.assertEqual(utils.encode_url('//A/N?Y=2', path='/B', params={'X': 1}), URL('//A/B?X=1'))
        self.assertEqual(utils.encode_url('//A/N?Y=2', params={'X': 1}), URL('//A/N?Y=2&X=1'))

    def test_str_path_raw(self):
        with patch('libka.utils.encode_data', return_value='ou') as mock:
            self.assertEqual(utils.encode_url('//A/N', path='/B', raw={'X': 1}), URL('//A/B?X=ou'))
            mock.assert_called_once_with(1)
        with patch('libka.utils.encode_data', return_value='ou') as mock:
            self.assertEqual(utils.encode_url('//A/N?Y=2', path='/B', raw={'X': 1}), URL('//A/B?X=ou'))
            mock.assert_called_once_with(1)
        with patch('libka.utils.encode_data', return_value='ou') as mock:
            self.assertEqual(utils.encode_url('//A/N?Y=2', raw={'X': 1}), URL('//A/N?Y=2&X=ou'))
            mock.assert_called_once_with(1)

    def test_url_path_none(self):
        self.assertEqual(utils.encode_url(utils.parse_url('A')),
                         URL.build(path='A'))
        self.assertEqual(utils.encode_url(utils.parse_url('A'), path=None),
                         URL.build(path='A'))

    def test_url_path_abs(self):
        self.assertEqual(utils.encode_url(utils.parse_url('A'), path='/B'),
                         URL.build(path='/B'))
        self.assertEqual(utils.encode_url(utils.parse_url('//A/N/m'), path='/B'),
                         URL.build(host='A', path='/B'))

    def test_url_path_rel(self):
        self.assertEqual(utils.encode_url(utils.parse_url('A'), path='B'),
                         URL.build(path='B'))
        self.assertEqual(utils.encode_url(utils.parse_url('/A'), path='B'),
                         URL.build(path='/B'))
        self.assertEqual(utils.encode_url(utils.parse_url('//A/N/m'), path='B'),
                         URL.build(host='A', path='/N/B'))

    def test_url_path_params(self):
        self.assertEqual(utils.encode_url(utils.parse_url('//A/N'), path='/B', params={'X': 1}),
                         URL.build(host='A', path='/B', query={'X': '1'}))
        self.assertEqual(utils.encode_url(utils.parse_url('//A/N?Y=2'), path='/B', params={'X': 1}),
                         URL.build(host='A', path='/B', query={'X': '1'}))
        self.assertEqual(utils.encode_url(utils.parse_url('//A/N?Y=2'), params={'X': 1}),
                         URL.build(host='A', path='/N', query={'Y': '2', 'X': '1'}))

    def test_url_path_raw(self):
        with patch('libka.utils.encode_data', return_value='ou') as mock:
            self.assertEqual(utils.encode_url(utils.parse_url('//A/N'), path='/B', raw={'X': 1}),
                             URL.build(host='A', path='/B', query={'X': 'ou'}))
            mock.assert_called_once_with(1)

        with patch('libka.utils.encode_data', return_value='ou') as mock:
            self.assertEqual(utils.encode_url(utils.parse_url('//A/N?Y=2'), path='/B', raw={'X': 1}),
                             URL.build(host='A', path='/B', query={'X': ['ou']}))
            mock.assert_called_once_with(1)
        with patch('libka.utils.encode_data', return_value='ou') as mock:
            self.assertEqual(utils.encode_url(utils.parse_url('//A/N?Y=2'), raw={'X': 1}),
                             URL.build(host='A', path='/N', query={'Y': ['2'], 'X': ['ou']}))
            mock.assert_called_once_with(1)

    def test_url_pathlib(self):
        self.assertEqual(utils.encode_url(utils.parse_url('//A/N/m'), path=Path('/B')),
                         URL.build(host='A', path='/B'))
        self.assertEqual(utils.encode_url(utils.parse_url('//A/N/m'), path=Path('B')),
                         URL.build(host='A', path='/N/B'))


class TestMain(TestCase):

    def test_main(self):
        import runpy
        sysmods = dict(sys.modules)
        del sysmods['libka.utils']
        with patch('runpy.sys.modules', sysmods):
            runpy.run_module('libka.utils', run_name='__main__')
