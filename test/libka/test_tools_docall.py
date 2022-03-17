
import sys
from pathlib import Path
import types
from unittest import TestCase
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'script.module.libka' / 'lib'))

from libka import tools  # noqa: E402
import libka             # noqa: E402


class E1(Exception):  pass  # noqa: E272, E701


class X1:  pass  # noqa: E272, E701
class X2:  pass  # noqa: E272, E701
class X3:  pass  # noqa: E272, E701
class X4:  pass  # noqa: E272, E701
class X5:  pass  # noqa: E272, E701


def fref(a):
    return a


def ffoo(m, a):
    return m(a)


class A:

    def __init__(self, n=0):
        self.n = n

    def __repr__(self):
        return f'A(n={self.n!r}, id={id(self)})'

    @staticmethod
    def sref(a):
        return a

    @classmethod
    def cref(cls, a):
        return cls, a

    def mref(self, a):
        return self, a

    @staticmethod
    def sfoo(m, a):
        return m(a)

    @classmethod
    def cfoo(cls, m, a):
        return m(cls, a)

    def mfoo(self, m, a):
        return m(self, a)


# def do_call(meth: Callable, args: Optional[Args] = None, kwargs: Optional[KwArgs] = None,
#             *, cls: Optional[Type] = None, obj: Optional[Any] = None, ref=None) -> Any:


class TestDoCall(TestCase):

    def test_args(self):
        def foo(*args, **kwargs): return args, kwargs
        self.assertTupleEqual(tools.do_call(foo)[0], ())
        self.assertDictEqual(tools.do_call(foo)[1], {})
        self.assertTupleEqual(tools.do_call(foo, ())[0], ())
        self.assertDictEqual(tools.do_call(foo, (), {})[1], {})
        self.assertTupleEqual(tools.do_call(foo, (X1,))[0], (X1,))
        self.assertDictEqual(tools.do_call(foo, (), {'x': X1})[1], {'x': X1})

    def test_descr(self):
        mock = MagicMock(return_value=2)
        self.assertEqual(tools.do_call(A.sfoo, (mock, 1)), 2)
        mock.assert_called_once_with(1)
        mock = MagicMock(return_value=2)
        a = A()
        self.assertEqual(tools.do_call(staticmethod(a.mfoo), (mock, 1)), 2)
        mock.assert_called_once_with(a, 1)

    def test_cls(self):
        def foo(cls): return (2, cls)
        with patch('libka.tools.get_class_that_defined_method', return_value=1) as mock:
            self.assertTupleEqual(tools.do_call(foo), (2, 1))
            mock.assert_called_once_with(foo)
        with patch('libka.tools.get_class_that_defined_method', return_value=1) as mock:
            self.assertTupleEqual(tools.do_call(foo, obj=X1()), (2, X1))
            mock.assert_not_called()
        with patch('libka.tools.get_class_that_defined_method', return_value=None) as mock:
            with self.assertRaises(TypeError):
                self.assertTupleEqual(tools.do_call(foo), (2, 1))
            mock.assert_called_once_with(foo)


class TestDoCallFunction(TestCase):

    def test_ref(self):
        with self.subTest('no ref'):
            mock = MagicMock(return_value=44)
            self.assertEqual(tools.do_call(ffoo, [mock, 42]), 44)
            mock.assert_called_once_with(42)
        with self.subTest('function'):
            mock = MagicMock(return_value=44)
            self.assertEqual(tools.do_call(ffoo, [mock, 42], ref=ffoo), 44)
            mock.assert_called_once_with(42)

    def test_ref_class(self):
        for ref in (A.sfoo, A.cfoo, A.mfoo, classmethod(A.mfoo), staticmethod(A.mfoo)):
            with self.subTest('class static method', ref=ref):
                mock = MagicMock(return_value=44)
                self.assertEqual(tools.do_call(ffoo, [mock, 42], ref=ref), 44)
                mock.assert_called_once_with(42)

    def test_ref_instance(self):
        for ref in (A().sfoo, A().cfoo, A().mfoo):
            with self.subTest('instance static method', ref=ref):
                mock = MagicMock(return_value=44)
                self.assertEqual(tools.do_call(ffoo, [mock, 42], ref=ref), 44)
                mock.assert_called_once_with(42)


class TestDoCallStaticMethod(TestCase):

    def test_ref(self):
        with self.subTest('no ref'):
            mock = MagicMock(return_value=44)
            self.assertEqual(tools.do_call(A.sfoo, [mock, 42]), 44)
            mock.assert_called_once_with(42)
        with self.subTest('function'):
            mock = MagicMock(return_value=44)
            self.assertEqual(tools.do_call(A.sfoo, [mock, 42], ref=ffoo), 44)
            mock.assert_called_once_with(42)

    def test_ref_class(self):
        for ref in (A.sfoo, A.cfoo, A.mfoo, classmethod(A.mfoo), staticmethod(A.mfoo)):
            with self.subTest('class static method', ref=ref):
                mock = MagicMock(return_value=44)
                self.assertEqual(tools.do_call(A.sfoo, [mock, 42], ref=ref), 44)
                mock.assert_called_once_with(42)

    def test_ref_instance(self):
        for ref in (A().sfoo, A().cfoo, A().mfoo):
            with self.subTest('instance static method', ref=ref):
                mock = MagicMock(return_value=44)
                self.assertEqual(tools.do_call(A.sfoo, [mock, 42], ref=ref), 44)
                mock.assert_called_once_with(42)


class TestDoCallClassMethod(TestCase):

    def test_ref(self):
        with self.subTest('no ref'):
            mock = MagicMock(return_value=44)
            self.assertEqual(tools.do_call(A.cfoo, [mock, 42]), 44)
            mock.assert_called_once_with(A, 42)
        with self.subTest('function'):
            mock = MagicMock(return_value=44)
            self.assertEqual(tools.do_call(A.cfoo, [mock, 42], ref=ffoo), 44)
            mock.assert_called_once_with(A, 42)

    def test_ref_class(self):
        for ref in (A.sfoo, A.cfoo, A.mfoo, classmethod(A.mfoo), staticmethod(A.mfoo)):
            with self.subTest('class static method', ref=ref):
                mock = MagicMock(return_value=44)
                self.assertEqual(tools.do_call(A.cfoo, [mock, 42], ref=ref), 44)
                mock.assert_called_once_with(A, 42)

    def test_ref_instance(self):
        for ref in (A().sfoo, A().cfoo, A().mfoo):
            with self.subTest('instance static method', ref=ref):
                mock = MagicMock(return_value=44)
                self.assertEqual(tools.do_call(A.cfoo, [mock, 42], ref=ref), 44)
                mock.assert_called_once_with(A, 42)


class TestDoCallMethod(TestCase):

    def test_ref(self):
        with self.subTest('no ref'):
            mock = MagicMock(return_value=44)
            with self.assertRaises(TypeError):
                self.assertEqual(tools.do_call(A.mfoo, [mock, 42]), 44)
            mock.assert_not_called()
        with self.subTest('function'):
            mock = MagicMock(return_value=44)
            with self.assertRaises(TypeError):
                self.assertEqual(tools.do_call(A.mfoo, [mock, 42], ref=ffoo), 44)
            mock.assert_not_called()

    def test_ref_class(self):
        mock = MagicMock(return_value=44)
        for ref in (A.sfoo, A.cfoo, A.mfoo, classmethod(A.mfoo), staticmethod(A.mfoo)):
            with self.subTest('class static method', ref=ref):
                mock = MagicMock(return_value=44)
                with self.assertRaises(TypeError):
                    self.assertEqual(tools.do_call(A.mfoo, [mock, 42], ref=ref), 44)
                mock.assert_not_called()

    def test_ref_instance(self):
        for ref in (A.sfoo, A.cfoo, A.mfoo):
            a = A()
            ref = types.MethodType(ref, a)
            with self.subTest('instance static method', ref=ref):
                mock = MagicMock(return_value=44)
                self.assertEqual(tools.do_call(A.mfoo, [mock, 42], ref=ref), 44)
                mock.assert_called_once_with(a, 42)
