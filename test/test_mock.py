# coding: utf-8

import asyncio
import functools
import inspect
import unittest
import sys

import asynctest

if sys.version_info >= (3, 5):
    from . import test_mock_await as _using_await
else:
    _using_await = None


def run_coroutine(coroutine):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


class Test:
    @asyncio.coroutine
    def a_coroutine(self):
        pass

    def a_function(self):
        pass

    def is_patched(self):
        return False

    a_dict = {'is_patched': False}

if _using_await:
    Test = _using_await.patch_Test_Class(Test)


patch_is_patched = functools.partial(asynctest.mock.patch,
                                     'test.test_mock.Test.is_patched',
                                     new=lambda self: True)


def inject_class(obj):
    # Decorate _Test_* mixin classes so we can retrieve the mock class to test
    # with the last argument of the test function ("klass").
    if isinstance(obj, type):
        for attr_name in dir(obj):
            attr = getattr(obj, attr_name)
            if callable(attr) and attr_name.startswith('test_'):
                setattr(obj, attr_name, inject_class(attr))

        return obj
    else:
        @functools.wraps(obj)
        def wrapper(self):
            return obj(self, getattr(asynctest, self.class_to_test))

        return wrapper


@inject_class
class _Test_iscoroutinefunction:
    # Ensure that an instance of this mock type is seen as a coroutine function
    def test_asyncio_iscoroutinefunction(self, klass):
        with self.subTest(is_coroutine=False):
            mock = klass(is_coroutine=False)
            self.assertFalse(asyncio.iscoroutinefunction(mock))

        with self.subTest(is_coroutine=False):
            mock = klass(is_coroutine=True)
            self.assertTrue(asyncio.iscoroutinefunction(mock))


@inject_class
class _Test_is_coroutine_property:
    # Ensure an instance offers an is_coroutine property
    def test_is_coroutine_property(self, klass):
        mock = klass()
        self.assertFalse(mock.is_coroutine)

        mock.is_coroutine = True
        self.assertTrue(mock.is_coroutine)

        mock = klass(is_coroutine=True)
        self.assertTrue(mock.is_coroutine)


@inject_class
class _Test_subclass:
    # Ensure that the tested class is also a subclass of its counterpart in
    # the standard module unittest.mock
    def test_subclass(self, klass):
        unittest_klass = getattr(unittest.mock, self.class_to_test)

        self.assertTrue(issubclass(klass, unittest_klass))
        self.assertTrue(isinstance(klass(), unittest_klass))


@inject_class
class _Test_called_coroutine:
    # Ensure that an object mocking as a coroutine works
    def test_returns_coroutine(self, klass):
        mock = klass()

        coro = mock()
        # Suppress debug warning about non-running coroutine
        if isinstance(coro, asyncio.coroutines.CoroWrapper):
            coro.gen = None

        self.assertTrue(asyncio.iscoroutine(coro))

    def test_returns_coroutine_from_return_value(self, klass):
        mock = klass()
        mock.return_value = 'ProbeValue'

        self.assertEqual('ProbeValue', mock.return_value)
        self.assertEqual(mock.return_value, run_coroutine(mock()))

    def test_returns_coroutine_with_return_value_being_a_coroutine(self, klass):
        mock = klass()
        coroutine = asyncio.coroutine(lambda: 'ProbeValue')
        mock.return_value = coroutine()

        self.assertEqual('ProbeValue', run_coroutine(mock()))

    def test_returns_coroutine_from_side_effect(self, klass):
        mock = klass()
        mock.side_effect = lambda: 'ProbeValue'

        self.assertEqual('ProbeValue', run_coroutine(mock()))

    def test_returns_coroutine_from_side_effect_being_a_coroutine(self, klass):
        mock = klass()
        mock.side_effect = asyncio.coroutine(lambda: 'ProbeValue')

        self.assertEqual('ProbeValue', run_coroutine(mock()))

    def test_exception_side_effect_raises_in_coroutine(self, klass):
        mock = klass()
        mock.side_effect = Exception

        coroutine = mock()
        with self.assertRaises(Exception):
            run_coroutine(coroutine)

    def test_returns_coroutine_from_side_effect_being_an_iterable(self, klass):
        mock = klass()
        side_effect = ['Probe1', 'Probe2', 'Probe3']
        mock.side_effect = side_effect

        for expected in side_effect:
            self.assertEqual(expected, run_coroutine(mock()))

        with self.assertRaises(StopIteration):
            mock()


@inject_class
class _Test_Spec_Spec_Set_Returns_Coroutine_Mock:
    # Ensure that when a mock is configured with spec or spec_set, coroutines
    # are detected and mocked correctly
    def test_mock_returns_coroutine_according_to_spec(self, klass):
        spec = Test()

        for attr in ('spec', 'spec_set', ):
            with self.subTest(spec_type=attr):
                mock = klass(**{attr: spec})

                self.assertIsInstance(mock.a_function, (asynctest.Mock, asynctest.MagicMock))
                self.assertNotIsInstance(mock.a_function, asynctest.CoroutineMock)
                self.assertIsInstance(mock.a_coroutine, asynctest.CoroutineMock)

                if _using_await:
                    self.assertIsInstance(mock.an_async_coroutine, asynctest.CoroutineMock)


class Test_NonCallabableMock(unittest.TestCase, _Test_subclass,
                             _Test_iscoroutinefunction,
                             _Test_is_coroutine_property,
                             _Test_Spec_Spec_Set_Returns_Coroutine_Mock):
    class_to_test = 'NonCallableMock'


class Test_NonCallableMagicMock(unittest.TestCase, _Test_subclass,
                                _Test_iscoroutinefunction,
                                _Test_is_coroutine_property,
                                _Test_Spec_Spec_Set_Returns_Coroutine_Mock):
    class_to_test = 'NonCallableMagicMock'


class Test_Mock(unittest.TestCase, _Test_subclass,
                _Test_Spec_Spec_Set_Returns_Coroutine_Mock):
    class_to_test = 'Mock'


class Test_MagicMock(unittest.TestCase, _Test_subclass,
                     _Test_Spec_Spec_Set_Returns_Coroutine_Mock):
    class_to_test = 'MagicMock'


class Test_CoroutineMock(unittest.TestCase, _Test_called_coroutine):
    class_to_test = 'CoroutineMock'

    def test_asyncio_iscoroutinefunction(self):
        mock = asynctest.mock.CoroutineMock()
        self.assertTrue(asyncio.iscoroutinefunction(mock))


class TestMockInheritanceModel(unittest.TestCase):
    to_test = {
        'NonCallableMagicMock': 'NonCallableMock',
        'Mock': 'NonCallableMock',
        'MagicMock': 'Mock',
        'CoroutineMock': 'Mock',
    }

    def test_Mock_is_not_CoroutineMock(self):
        self.assertNotIsInstance(asynctest.mock.Mock(), asynctest.mock.CoroutineMock)

    def test_MagicMock_is_not_CoroutineMock(self):
        self.assertNotIsInstance(asynctest.mock.MagicMock(), asynctest.mock.CoroutineMock)

    @staticmethod
    def make_inheritance_test(child, parent):
        def test(self):
            # Works in the common case
            self.assertIsInstance(getattr(asynctest.mock, child)(),
                                  getattr(asynctest.mock, parent))

            # Works with a custom spec
            self.assertIsInstance(getattr(asynctest.mock, child)(Test()),
                                  getattr(asynctest.mock, parent))

        return test

for child, parent in TestMockInheritanceModel.to_test.items():
    setattr(TestMockInheritanceModel,
            'test_{}_inherits_from_{}'.format(child, parent),
            TestMockInheritanceModel.make_inheritance_test(child, parent))


class Test_mock_open(unittest.TestCase):
    def test_MagicMock_returned_by_default(self):
        self.assertIsInstance(asynctest.mock_open(), asynctest.MagicMock)


class Test_patch(unittest.TestCase):
    def test_patch_with_MagicMock(self):
        with asynctest.mock.patch('test.test_mock.Test') as mock:
            self.assertIsInstance(mock, asynctest.mock.MagicMock)

        with asynctest.mock.patch('test.test_mock.Test.a_function') as mock:
            self.assertIsInstance(mock, asynctest.mock.MagicMock)

    def test_patch_decorate_with_MagicMock(self):
        @asynctest.mock.patch('test.test_mock.Test')
        def test_mock_class(mock):
            self.assertIsInstance(mock, asynctest.mock.MagicMock)

        @asynctest.mock.patch('test.test_mock.Test.a_function')
        def test_mock_function(mock):
            self.assertIsInstance(mock, asynctest.mock.MagicMock)

        test_mock_class()
        test_mock_function()

    def test_patch_decorate_coroutine_function_with_CoroutineMock(self):
        @asynctest.mock.patch('test.test_mock.Test.a_coroutine')
        def test_mock_coroutine(mock):
            self.assertIsInstance(mock, asynctest.mock.CoroutineMock)

        test_mock_coroutine()

    if _using_await:
        def test_patch_async_coroutine_function_with_CoroutineMock(self):
            with asynctest.mock.patch('test.test_mock.Test.an_async_coroutine') as mock:
                self.assertIsInstance(mock, asynctest.mock.CoroutineMock)

        def test_patch_decorate_async_coroutine_function_with_CoroutineMock(self):
            @asynctest.mock.patch('test.test_mock.Test.an_async_coroutine')
            def test_mock_coroutine(mock):
                self.assertIsInstance(mock, asynctest.mock.CoroutineMock)

            test_mock_coroutine()

    def test_patch_decorates_coroutine(self):
        @asyncio.coroutine
        def a_coroutine():
            import test.test_mock
            return test.test_mock.Test().is_patched()

        coroutines = [a_coroutine]
        if _using_await:
            coroutines.append(_using_await.transform(a_coroutine))

        for coroutine in coroutines:
            with self.subTest(coroutine=coroutine):
                self.assertTrue(run_coroutine(patch_is_patched()(coroutine)()))

    def test_patch_decorates_function(self):
        @patch_is_patched()
        def a_function():
            import test.test_mock
            return test.test_mock.Test().is_patched()

        self.assertTrue(a_function())


class Test_patch_decorator_coroutine_or_generator(unittest.TestCase):
    def test_generator_type_when_patched(self):
        def a_generator():
            yield

        a_patched_generator = patch_is_patched()(a_generator)

        self.assertTrue(inspect.isgeneratorfunction(a_generator))
        self.assertTrue(inspect.isgenerator(a_generator()))
        self.assertEqual(asyncio.iscoroutinefunction(a_patched_generator),
                         asyncio.iscoroutinefunction(a_generator))

    def test_coroutine_type_when_patched(self):
        @asyncio.coroutine
        def a_coroutine():
            pass

        a_patched_coroutine = patch_is_patched()(a_coroutine)

        self.assertEqual(asyncio.iscoroutinefunction(a_patched_coroutine),
                         asyncio.iscoroutinefunction(a_coroutine))
        self.assertEqual(inspect.isgeneratorfunction(a_patched_coroutine),
                         inspect.isgeneratorfunction(a_coroutine))
        coro = a_coroutine()
        patched_coro = a_patched_coroutine()
        try:
            self.assertEqual(asyncio.iscoroutine(patched_coro),
                             asyncio.iscoroutine(coro))
        finally:
            run_coroutine(coro)
            run_coroutine(patched_coro)

        if not _using_await:
            return

        a_coroutine = _using_await.transform(a_coroutine)
        a_patched_coroutine = patch_is_patched()(a_coroutine)
        self.assertEqual(asyncio.iscoroutinefunction(a_patched_coroutine),
                         asyncio.iscoroutinefunction(a_coroutine))
        coro = a_coroutine()
        patched_coro = a_patched_coroutine()
        try:
            self.assertEqual(asyncio.iscoroutine(patched_coro),
                             asyncio.iscoroutine(coro))
        finally:
            run_coroutine(coro)
            run_coroutine(patched_coro)

    def is_patched(self):
        import test.test_mock
        return test.test_mock.Test().is_patched()

    def test_patch_generator_only_when_running(self):
        @patch_is_patched()
        def a_generator():
            yield self.is_patched()
            yield self.is_patched()

        gen = a_generator()
        self.assertTrue(next(gen))
        self.assertFalse(self.is_patched())
        self.assertTrue(next(gen))

    def test_patch_coroutine_only_when_running(self):
        def set_fut_result(fut):
            fut.set_result(self.is_patched())

        @asyncio.coroutine
        def tester(coro_function):
            loop = asyncio.get_event_loop()
            fut = asyncio.Future(loop=loop)
            loop.call_soon(set_fut_result, fut)
            before, after = yield from coro_function(fut)
            self.assertTrue(before)
            self.assertFalse(fut.result())
            self.assertTrue(after)

        with self.subTest("old style coroutine"):
            @patch_is_patched()
            def a_coroutine(fut):
                before = self.is_patched()
                yield from fut
                after = self.is_patched()
                return before, after

            run_coroutine(tester(a_coroutine))

        if not _using_await:
            return

        with self.subTest("new style coroutine"):
            a_new_style_coroutine = _using_await.build_simple_coroutine(
                self.is_patched)
            a_new_style_coroutine = patch_is_patched()(a_new_style_coroutine)
            run_coroutine(tester(a_new_style_coroutine))

    def test_generator_arg_is_default_mock(self):
        @asynctest.mock.patch('test.test_mock.Test')
        def a_generator(mock):
            self.assertIsInstance(mock, asynctest.mock.Mock)
            yield
            import test.test_mock
            self.assertIs(mock, test.test_mock.Test)

        for _ in a_generator():
            pass

    def test_coroutine_arg_is_default_mock(self):
        @asyncio.coroutine
        def tester(coroutine_function):
            loop = asyncio.get_event_loop()
            fut = asyncio.Future(loop=loop)
            loop.call_soon(fut.set_result, None)
            before, after = yield from coroutine_function(fut)
            self.assertTrue(before)
            self.assertTrue(after)

        def is_instance_of_mock(obj):
            return isinstance(obj, asynctest.mock.Mock)

        def is_same_mock(obj):
            import test.test_mock
            return obj is test.test_mock.Test

        with self.subTest("old style coroutine"):
            @asynctest.mock.patch('test.test_mock.Test')
            def a_coroutine(fut, mock):
                before = is_instance_of_mock(mock)
                yield from fut
                after = is_same_mock(mock)
                return before, after

            run_coroutine(tester(a_coroutine))

        if not _using_await:
            return

        with self.subTest("new style coroutine"):
            a_new_style_coroutine = _using_await.build_simple_coroutine(
                is_instance_of_mock, is_same_mock)
            a_new_style_coroutine = asynctest.mock.patch(
                'test.test_mock.Test')(a_new_style_coroutine)
            run_coroutine(tester(a_new_style_coroutine))


class Test_patch_object(unittest.TestCase):
    def test_patch_with_MagicMock(self):
        with asynctest.mock.patch.object(Test(), 'a_function') as mock:
            self.assertIsInstance(mock, asynctest.mock.MagicMock)

        obj = Test()
        obj.test = Test()
        with asynctest.mock.patch.object(obj, 'test') as mock:
            self.assertIsInstance(mock, asynctest.mock.MagicMock)

    def test_patch_coroutine_function_with_CoroutineMock(self):
        with asynctest.mock.patch.object(Test(), 'a_coroutine') as mock:
            self.assertIsInstance(mock, asynctest.mock.CoroutineMock)

        if _using_await:
            with asynctest.mock.patch.object(Test(), 'an_async_coroutine') as mock:
                self.assertIsInstance(mock, asynctest.mock.CoroutineMock)

    def test_patch_decorates_coroutine(self):
        obj = Test()

        patch = functools.partial(asynctest.mock.patch.object,
                                  obj, 'is_patched', new=lambda: True)

        @asyncio.coroutine
        def a_coroutine():
            return obj.is_patched()

        coroutines = [a_coroutine]
        if _using_await:
            coroutines.append(_using_await.transform(a_coroutine))

        for coroutine in coroutines:
            with self.subTest(coroutine=coroutine):
                self.assertTrue(run_coroutine(patch()(coroutine)()))


class Test_patch_multiple(unittest.TestCase):
    def test_patch_with_MagicMock(self):
        default = asynctest.mock.DEFAULT
        with asynctest.mock.patch.multiple('test.test_mock', Test=default):
            import test.test_mock
            self.assertIsInstance(test.test_mock.Test, asynctest.mock.MagicMock)

    def test_patch_coroutine_function_with_CoroutineMock(self):
        default = asynctest.mock.DEFAULT

        also_patch = {}
        if _using_await:
            also_patch['an_async_coroutine'] = default

        with asynctest.mock.patch.multiple('test.test_mock.Test',
                                           a_function=default,
                                           a_coroutine=default,
                                           **also_patch):
            import test.test_mock
            obj = test.test_mock.Test()
            self.assertIsInstance(obj.a_function, asynctest.mock.MagicMock)
            self.assertIsInstance(obj.a_coroutine, asynctest.mock.CoroutineMock)

            if _using_await:
                self.assertIsInstance(obj.an_async_coroutine, asynctest.mock.CoroutineMock)

    def test_patch_decorates_coroutine(self):
        patch = functools.partial(asynctest.mock.patch.multiple,
                                  'test.test_mock.Test',
                                  is_patched=lambda self: True)

        @asyncio.coroutine
        def a_coroutine():
            import test.test_mock
            return test.test_mock.Test().is_patched()

        coroutines = [a_coroutine]
        if _using_await:
            coroutines.append(_using_await.transform(a_coroutine))

        for coroutine in coroutines:
            with self.subTest(coroutine=coroutine):
                self.assertTrue(run_coroutine(patch()(coroutine)()))


class Test_patch_dict(unittest.TestCase):
    def test_patch_decorates_coroutine(self):
        patch = functools.partial(asynctest.mock.patch.dict,
                                  'test.test_mock.Test.a_dict',
                                  is_patched=True)

        @asyncio.coroutine
        def a_coroutine():
            import test.test_mock
            return test.test_mock.Test().a_dict['is_patched']

        coroutines = [a_coroutine]

        if _using_await:
            coroutines.append(_using_await.transform(a_coroutine))

        for coroutine in coroutines:
            with self.subTest(coroutine=coroutine):
                self.assertTrue(run_coroutine(patch()(coroutine)()))

    def test_patch_decorates_function(self):
        @asynctest.mock.patch.dict('test.test_mock.Test.a_dict', is_patched=True)
        def a_function():
            import test.test_mock
            return test.test_mock.Test().a_dict['is_patched']

        self.assertTrue(a_function())


class Test_return_once(unittest.TestCase):
    def test_default_value(self):
        iterator = asynctest.mock.return_once("ProbeValue")
        self.assertEqual("ProbeValue", next(iterator))
        for _ in range(3):
            self.assertIsNone(next(iterator))

    def test_then(self):
        iterator = asynctest.mock.return_once("ProbeValue", "ThenValue")
        self.assertEqual("ProbeValue", next(iterator))
        for _ in range(2):
            self.assertEqual("ThenValue", next(iterator))

        iterator = asynctest.mock.return_once("ProbeValue", then="ThenValue")
        self.assertEqual("ProbeValue", next(iterator))
        self.assertEqual("ThenValue", next(iterator))

    def test_with_side_effect_default(self):
        mock = asynctest.Mock(side_effect=asynctest.mock.return_once("ProbeValue"))
        self.assertEqual("ProbeValue", mock())
        for _ in range(3):
            self.assertIsNone(mock())

    def test_with_side_effect_then(self):
        side_effect = asynctest.mock.return_once("ProbeValue", "ThenValue")
        mock = asynctest.Mock(side_effect=side_effect)
        self.assertEqual("ProbeValue", mock())
        for _ in range(2):
            self.assertEqual("ThenValue", mock())

    def test_with_side_effect_raises(self):
        mock = asynctest.mock.Mock(side_effect=asynctest.mock.return_once(Exception))
        self.assertRaises(Exception, mock)
        self.assertIsNone(mock())

    def test_with_side_effect_raises_then(self):
        side_effect = asynctest.mock.return_once("ProbeValue", BlockingIOError)
        mock = asynctest.mock.Mock(side_effect=side_effect)
        self.assertEqual("ProbeValue", mock())
        for _ in range(2):
            self.assertRaises(BlockingIOError, mock)

    def test_with_side_effect_raises_all(self):
        side_effect = asynctest.mock.return_once(Exception, BlockingIOError)
        mock = asynctest.mock.Mock(side_effect=side_effect)
        self.assertRaises(Exception, mock)
        for _ in range(2):
            self.assertRaises(BlockingIOError, mock)


if __name__ == "__main__":
    unittest.main()
