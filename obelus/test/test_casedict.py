
import unittest

from obelus.casedict import CaseDict
from obelus.test import main


class CaseDictTest(unittest.TestCase):

    def check_underlying_dict(self, d, expected):
        """
        Check for implementation details.
        """
        self.assertEqual(set(d._data), set(expected))
        self.assertEqual({k: d[k] for k in d._data}, expected)
        self.assertEqual(len(d._data), len(expected))

    # NOTE: we only test the operations which are not inherited from
    # MutableMapping.

    def test_init(self):
        d = CaseDict()
        self.check_underlying_dict(d, {})
        d = CaseDict({'Foo': 5, 'baR': 6})
        self.check_underlying_dict(d, {'foo': 5, 'bar': 6})
        d = CaseDict(fOO=5, Bar=6)
        self.check_underlying_dict(d, {'foo': 5, 'bar': 6})
        d = CaseDict({'FOO': 5}, Bar=6)
        self.check_underlying_dict(d, {'foo': 5, 'bar': 6})

    def test_setitem_getitem(self):
        d = CaseDict()
        with self.assertRaises(KeyError):
            d['foo']
        d['Foo'] = 5
        self.assertEqual(d['foo'], 5)
        self.assertEqual(d['Foo'], 5)
        self.assertEqual(d['FOo'], 5)
        with self.assertRaises(KeyError):
            d['bar']
        self.check_underlying_dict(d, {'foo': 5})
        d['BAR'] = 6
        self.assertEqual(d['Bar'], 6)
        self.check_underlying_dict(d, {'foo': 5, 'bar': 6})
        # Overwriting
        d['foO'] = 7
        self.assertEqual(d['foo'], 7)
        self.assertEqual(d['Foo'], 7)
        self.assertEqual(d['FOo'], 7)
        self.check_underlying_dict(d, {'foo': 7, 'bar': 6})

    def test_delitem(self):
        d = CaseDict(Foo=5)
        d['baR'] = 3
        del d['fOO']
        self.check_underlying_dict(d, {'bar': 3})
        with self.assertRaises(KeyError):
            del d['Foo']
        with self.assertRaises(KeyError):
            del d['foo']

    def test_get(self):
        d = CaseDict()
        default = object()
        self.assertIs(d.get('foo'), None)
        self.assertIs(d.get('foo', default), default)
        d['Foo'] = 5
        self.assertEqual(d.get('foo'), 5)
        self.assertEqual(d.get('FOO'), 5)
        self.assertIs(d.get('bar'), None)
        self.check_underlying_dict(d, {'foo': 5})

    def test_pop(self):
        d = CaseDict()
        default = object()
        with self.assertRaises(KeyError):
            d.pop('foo')
        self.assertIs(d.pop('foo', default), default)
        d['Foo'] = 5
        self.assertIn('foo', d)
        self.assertEqual(d.pop('foo'), 5)
        self.assertNotIn('foo', d)
        self.check_underlying_dict(d, {})
        d['Foo'] = 5
        self.assertIn('Foo', d)
        self.assertEqual(d.pop('FOO'), 5)
        self.assertNotIn('foo', d)
        self.check_underlying_dict(d, {})
        with self.assertRaises(KeyError):
            d.pop('foo')

    def test_clear(self):
        d = CaseDict()
        d.clear()
        self.check_underlying_dict(d, {})
        d['Foo'] = 5
        d['baR'] = 3
        self.check_underlying_dict(d, {'foo': 5, 'bar': 3})
        d.clear()
        self.check_underlying_dict(d, {})

    def test_contains(self):
        d = CaseDict()
        self.assertIs(False, 'foo' in d)
        d['Foo'] = 5
        self.assertIs(True, 'Foo' in d)
        self.assertIs(True, 'foo' in d)
        self.assertIs(True, 'FOO' in d)
        self.assertIs(False, 'bar' in d)

    def test_len(self):
        d = CaseDict()
        self.assertEqual(len(d), 0)
        d['Foo'] = 5
        self.assertEqual(len(d), 1)
        d['BAR'] = 6
        self.assertEqual(len(d), 2)
        d['foo'] = 7
        self.assertEqual(len(d), 2)
        d['baR'] = 3
        self.assertEqual(len(d), 2)
        del d['Bar']
        self.assertEqual(len(d), 1)

    def test_iter(self):
        d = CaseDict()
        it = iter(d)
        with self.assertRaises(StopIteration):
            next(it)
        d['Foo'] = 5
        d['BAR'] = 6
        yielded = []
        for x in d:
            yielded.append(x)
        self.assertEqual(set(yielded), {'Foo', 'BAR'})

    def test_repr(self):
        d = CaseDict()
        self.assertEqual(repr(d), "CaseDict()")
        d['Foo'] = 5
        self.assertEqual(repr(d), "CaseDict({'Foo': 5})")
        d['Bar'] = 6
        self.assertIn(repr(d), ("CaseDict({'Foo': 5, 'Bar': 6})",
                                "CaseDict({'Bar': 6, 'Foo': 5})"))


if __name__ == "__main__":
    main()
