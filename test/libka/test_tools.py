
import sys
from pathlib import Path
import inspect
from unittest import TestCase
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'script.module.libka' / 'lib'))

from libka import tools  # noqa: E402
import libka             # noqa: E402


class E1(Exception):  pass  # noqa: E272, E701


class X1:  pass  # noqa: E272, E701
class X2:  pass  # noqa: E272, E701
class X3:  pass  # noqa: E272, E701
class X4:  pass  # noqa: E272, E701
class X5:  pass  # noqa: E272, E701


class TestADict(TestCase):

    def test_type(self):
        self.assertIsInstance(tools.adict(), dict)

    def test_dict_methods(self):
        for k in dir(dict):
            # I don't know why `fromkeys` are differ
            if k not in {'__class__', '__class_getitem__', '__doc__', '__init_subclass__', '__subclasshook__',
                         'fromkeys'}:
                self.assertIs(getattr(tools.adict, k), getattr(dict, k))

    def test_attr(self):
        self.assertIs(tools.adict((('a', X1),)).a, X1)
        self.assertIsNone(tools.adict((('a', X1),)).b)

    def test_dict(self):
        d = {1: 2, 3: 4}
        self.assertDictEqual(tools.adict(d), d)

    def test_pikle(self):
        self.assertIs(type(tools.adict().__getstate__()), dict)
        with patch('libka.tools.dict') as mock_dict:
            x = libka.tools.adict()
            x.__getstate__()
            mock_dict.assert_called_once_with(x)


class TestMkMDict(TestCase):

    def test_mkmdict(self):
        self.assertDictEqual(tools.mkmdict(()), {})
        self.assertDictEqual(tools.mkmdict(((1, 2),)), {1: [2]})
        self.assertDictEqual(tools.mkmdict(((1, 2), (1, 3))), {1: [2, 3]})


class TestItemIter(TestCase):

    def test_value(self):
        self.assertTupleEqual(tools.item_iter(None), ())
        self.assertIs(tools.item_iter(X1), X1)

    def test_seq(self):
        d = {1: 2}
        self.assertEqual(tools.item_iter(d), d.items())
        self.assertIs(type(tools.item_iter(d)), type(d.items()))


class TestGetAttr(TestCase):

    def test_empty(self):
        false = MagicMock()
        false.__bool__.return_value = False
        self.assertIsNone(tools.get_attr(X1, None))
        self.assertIsNone(tools.get_attr(X1, false))

    def test_args(self):
        self.assertIs(tools.get_attr(None, None, default=X1), X1)
        with patch('libka.tools.getattr', return_value=X1) as mock:
            self.assertIs(tools.get_attr(X1, 'a:b', sep=':'), X1)
            mock.assert_has_calls([
                call(X1, 'a'),
                call(X1, 'b'),
            ])

    def test_obj_name(self):
        with patch('libka.tools.getattr', return_value=X3) as mock:
            self.assertIs(tools.get_attr(X1, 'a'), X3)
            mock.assert_called_once_with(X1, 'a')
        with patch('libka.tools.getattr', return_value=X3) as mock:
            self.assertIs(tools.get_attr(X1, 'a.b'), X3)
            mock.assert_has_calls([
                call(X1, 'a'),
                call(X3, 'b'),
            ])

    def test_obj_attr(self):
        with patch('libka.tools.getattr', return_value=X3) as mock:
            self.assertIs(tools.get_attr(X1, [X2]), X3)
            mock.assert_called_once_with(X1, X2)
        with patch('libka.tools.getattr', side_effect=E1) as mock:
            with self.assertRaises(E1):
                tools.get_attr(X1, [X2])
            mock.assert_called_once_with(X1, X2)
        with patch('libka.tools.getattr', side_effect=AttributeError) as mock:
            self.assertIs(tools.get_attr(X1, [X2], default=X3), X3)
            mock.assert_called_once_with(X1, X2)

    def test_global_attr(self):
        with patch('libka.tools.globals', return_value={'a': X3}) as mock:
            self.assertIs(tools.get_attr(None, 'a'), X3)
            mock.assert_called_once_with()
        with patch('libka.tools.globals', return_value={'x': X3}) as mock:
            self.assertIs(tools.get_attr(None, 'a', default=X2), X2)
            mock.assert_called_once_with()
        with (patch('libka.tools.globals', return_value={'a': X2}) as mock_globals,
              patch('libka.tools.getattr', return_value=X3) as mock_getattr):
            self.assertIs(tools.get_attr(None, 'a.b'), X3)
            mock_globals.assert_called_once_with()
            mock_getattr.assert_called_once_with(X2, 'b')


class TestSetDefaultX(TestCase):

    def test_empty(self):
        d = {}
        self.assertIs(tools.setdefaultx(d, 'a', None, 42), d)
        self.assertDictEqual(d, {'a': 42})

    def test_exists(self):
        d = {'a': 1}
        self.assertIs(tools.setdefaultx(d, 'a', None, 42), d)
        self.assertDictEqual(d, {'a': 1})

    def test_none(self):
        d = {}
        self.assertIs(tools.setdefaultx(d, 'a', None, None), d)
        self.assertDictEqual(d, {})


class TestXStrIter(TestCase):

    def test_xit(self):
        self.assertTrue(inspect.isgeneratorfunction(tools.xstriter))
        self.assertListEqual(list(tools.xstriter(1, 2, 3)), ['1', '2', '3'])
        self.assertListEqual(list(tools.xstriter(0, 2, None)), ['2'])


class AaaDescr:
    def __get__(self, instance, owner):
        pass


class Aaa:
    def foo(self): pass
    bar = property(foo)
    baz = AaaDescr()
    @classmethod
    def clsmeth(cls): pass
    @staticmethod
    def static(): pass


def foo(): pass


class TestGetClassThatDefinedMethod(TestCase):

    def test(self):
        from functools import partial
        self.assertIs(tools.get_class_that_defined_method(Aaa().foo), Aaa)
        self.assertIs(tools.get_class_that_defined_method(Aaa.foo), Aaa)
        self.assertIs(tools.get_class_that_defined_method(Aaa.bar), Aaa)
        self.assertIsNone(tools.get_class_that_defined_method(Aaa.baz))
        self.assertIs(tools.get_class_that_defined_method(Aaa.clsmeth), Aaa)
        self.assertIs(tools.get_class_that_defined_method(Aaa.static), Aaa)
        self.assertIs(tools.get_class_that_defined_method(partial(Aaa.foo)), Aaa)
        self.assertIs(tools.get_class_that_defined_method(staticmethod(Aaa.foo)), Aaa)
        self.assertIsNone(tools.get_class_that_defined_method(foo))


class TestCopyFunction(TestCase):

    def test_default(self):
        def foo(): pass
        self.assertEqual(tools.copy_function(foo).__code__, foo.__code__)
        self.assertIs(tools.copy_function(foo).__globals__, foo.__globals__)

    def test_globals(self):
        def foo(): pass
        self.assertEqual(tools.copy_function(foo, globals=True).__code__, foo.__code__)
        self.assertDictEqual(tools.copy_function(foo, globals=True).__globals__, foo.__globals__)
        self.assertIsNot(tools.copy_function(foo, globals=True).__globals__, foo.__globals__)

    def test_dict(self):
        def foo(): pass
        g = {'a': 42}
        self.assertEqual(tools.copy_function(foo, globals=g).__code__, foo.__code__)
        self.assertIs(tools.copy_function(foo, globals=g).__globals__, g)

    def test_module(self):
        def foo(): pass
        self.assertEqual(tools.copy_function(foo, module=X1).__code__, foo.__code__)
        self.assertIs(tools.copy_function(foo, module=X1).__module__, X1)


class TestWrapsClass(TestCase):

    class X:
        foo = 42

    def test_deco(self):
        self.assertTrue(callable(tools.wraps_class(TestWrapsClass.X)))

    def test_wrapper(self):
        with patch('libka.tools.WRAPPER_ASSIGNMENTS', ['foo']):
            class Y:
                foo = 1
            deco = tools.wraps_class(TestWrapsClass.X)
            deco(Y)
            self.assertEqual(Y.foo, TestWrapsClass.X.foo)

    def test_missing(self):
        with patch('libka.tools.WRAPPER_ASSIGNMENTS', ['bar', 'foo']):
            class Y:
                foo = 1
            deco = tools.wraps_class(TestWrapsClass.X)
            deco(Y)
            self.assertEqual(Y.foo, TestWrapsClass.X.foo)


class TestCallDescr(TestCase):

    def test_make(self):
        mock = MagicMock(return_value=X1)
        d = tools.CallDescr(mock)
        self.assertIs(tools.CallDescr.make(d), d)

    def test_repr(self):
        mock = MagicMock(return_value=X1, __repr__=lambda x: 'abc')
        self.assertEqual(repr(tools.CallDescr(mock, (1,), {'b': 2})), "CallDescr(abc, 1, b=2)")

    def test_self(self):
        class A:
            def foo(self): pass
        def foo(): pass
        a = A()
        self.assertIs(tools.CallDescr(a.foo).self, a)
        with patch('libka.tools.CallDescr._get_arg', return_value=X1) as mock:
            self.assertIs(tools.CallDescr(foo).self, X1)
            mock.assert_called_once_with('self')

    def test_cls(self):
        class A:
            @classmethod
            def cls(cls): pass
            def foo(self): pass
        def foo(): pass
        a = A()
        self.assertIs(tools.CallDescr(a.cls).cls, A)
        self.assertIs(tools.CallDescr(a.foo).cls, A)
        with patch('libka.tools.CallDescr._get_arg', return_value=X1()) as mock:
            self.assertIs(tools.CallDescr(A.foo).cls, X1)
            mock.assert_called_once_with('self')
        with patch('libka.tools.CallDescr._get_arg', return_value=X1) as mock:
            self.assertIs(tools.CallDescr(foo).cls, X1)
            mock.assert_called_once_with('cls')

    def test_get_arg(self):
        def foo(abc): pass
        def bar(abc=None): pass
        self.assertIs(tools.CallDescr(foo, (X1,))._get_arg('abc'), X1)
        self.assertIs(tools.CallDescr(bar, (), {'abc': X1})._get_arg('abc'), X1)

