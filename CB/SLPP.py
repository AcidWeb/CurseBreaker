# This module is adapted by layday <https://github.com/layday> from SLPP <https://github.com/SirAnthony/slpp>.
#
#   Copyright (c) 2010, 2011, 2012 SirAnthony <anthony at adsorbtion.org>
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files (the "Software"), to deal
#   in the Software without restriction, including without limitation the rights
#   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#   copies of the Software, and to permit persons to whom the Software is
#   furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#   THE SOFTWARE.

from __future__ import annotations

import re
import string
from collections.abc import Container
from itertools import count, islice
from operator import eq
from typing import Any

DIGITS = frozenset(string.digits)
HEXDIGITS = frozenset(string.hexdigits)
HEXDELIMS = frozenset('Xx')
EXPONENTS = frozenset('Ee')
WHITESPACE = frozenset(string.whitespace)
WHITESPACE_OR_CLOSING_SQ_BR = WHITESPACE | frozenset(']')
NEWLINE = frozenset('\r\n')

match_bare_word = re.compile(r'^[a-z_]\w*$', flags=re.IGNORECASE)


class ParseError(Exception):
    pass


class _Sentinel(str):
    pass


_sentinel = _Sentinel()


class _SLPP:
    def __init__(self, text: str):
        self._iter_text = iter(text)
        self._next()

    def _next(self):
        self.c = next(self._iter_text, _sentinel)

    def _next_eq(self, includes: Container[str]):
        if self.c not in includes:
            for c in self._iter_text:
                if c in includes:
                    self.c = c
                    break
            else:
                self.c = _sentinel

    def _next_not_eq(self, excludes: Container[str]):
        if self.c in excludes:
            for c in self._iter_text:
                if c not in excludes:
                    self.c = c
                    break
            else:
                self.c = _sentinel

    def _decode_table(self):
        table: dict[Any, Any] | list[Any] = {}
        idx = 0

        self._next()
        while True:
            self._next_not_eq(WHITESPACE)

            if self.c == '}':
                # Convert table to list if k(0) = 1 and k = k(n-1) + 1, ...
                if (
                    table
                    and all(map(eq, table, count(1)))
                    # bool is a subclass of int in Python but not in Lua
                    and not any(isinstance(k, bool) for k in islice(table, 0, 2))
                ):
                    table = list(table.values())

                self._next()
                return table

            elif self.c == ',':
                self._next()

            else:
                is_val_long_string_literal = False

                if self.c == '[':
                    self._next()
                    if self.c == '[':
                        is_val_long_string_literal = True

                item = self.decode()
                self._next_not_eq(WHITESPACE_OR_CLOSING_SQ_BR)

                c = self.c
                if c and c in '=,':
                    self._next()

                    if c == '=':
                        if is_val_long_string_literal:
                            raise ParseError('malformed key', item)

                        # nil key produces a runtime error in Lua
                        if item is None:
                            raise ParseError('table keys cannot be nil')

                        # Item is a key
                        value = self.decode()
                        if (
                            # nil values are not persisted in Lua tables
                            value is not None
                            # Where the key is a valid index key-less values take precedence
                            and (not isinstance(item, int) or isinstance(item, bool) or item > idx)
                        ):
                            table[item] = value
                        continue

                if item is not None:
                    idx += 1
                    table[idx] = item

    def _decode_string(self):
        s = ''
        start = self.c
        end = None
        prev_was_slash = False

        if start == '[':
            self._next_not_eq('[')
            s += self.c
            end = ']'
        else:
            end = start

        for c in self._iter_text:
            if prev_was_slash:
                prev_was_slash = False

                if c != end:
                    s += '\\'
            elif c == end:
                break
            elif c == '\\' and start == end:
                prev_was_slash = True
                continue

            s += c

        self._next()
        if start != end:
            # Strip multiple closing brackets
            self._next_not_eq(end)

        return s

    def _decode_bare_word(self):
        s = self.c
        for c in self._iter_text:
            new_s = s + c
            if match_bare_word.match(new_s):
                s = new_s
            else:
                break

        self._next()

        if s == 'true':
            return True
        elif s == 'false':
            return False
        elif s == 'nil':
            return None
        return s

    def _decode_number(self):
        def get_digits():
            n = ''

            for c in self._iter_text:
                if c in DIGITS:
                    n += c
                else:
                    self.c = c
                    break
            else:
                self.c = _sentinel

            return n

        n = ''

        if self.c == '-':
            c = self.c
            self._next()
            if self.c == '-':
                # This is a comment - skip to the end of the line
                self._next_eq(NEWLINE)
                return None

            elif not self.c or self.c not in DIGITS:
                raise ParseError('malformed number (no digits after minus sign)', c + self.c)

            n += c

        n += self.c + get_digits()
        if n == '0' and self.c in HEXDELIMS:
            n += self.c

            for c in self._iter_text:
                if c in HEXDIGITS:
                    n += c
                else:
                    self.c = c
                    break
            else:
                self.c = _sentinel

        else:
            if self.c == '.':
                n += self.c + get_digits()

            if self.c in EXPONENTS:
                n += self.c
                self._next()  # +-
                n += self.c + get_digits()

        try:
            return int(n, 0)
        except ValueError:
            return float(n)

    def decode(self):
        self._next_not_eq(WHITESPACE)
        if not self.c:
            raise ParseError('input is empty')
        elif self.c == '{':
            return self._decode_table()
        elif self.c in '\'"[':
            return self._decode_string()
        elif self.c == '-' or self.c in DIGITS:
            return self._decode_number()
        else:
            return self._decode_bare_word()


def loads(s: str) -> Any:
    return _SLPP(s).decode()
