import os
import sys
import platform
from terminaltables.ascii_table import AsciiTable

system = platform.system()

if system == 'Windows':
    import msvcrt
else:
    from select import select


def pause():
    if system == 'Windows':
        os.system('pause')
    else:
        os.system('/bin/bash -c "read -rsp $\'Press any key to continue . . .\n\' -n 1"')


def timeout():
    if system == 'Windows':
        os.system('timeout /t 5')
    else:
        os.system('/bin/bash -c "read -rsp $\'Waiting for 5 seconds, press a key to continue ...\n\' -n 1 -t 5"')


def clear():
    if system == 'Windows':
        os.system('cls')
    else:
        os.system('clear')


def set_terminal_title(title):
    if system == 'Windows':
        os.system(f'title {title}')
    else:
        os.system(f'echo "\033]0;{title}\007"')


def set_terminal_size(w, h):
    if system == 'Windows':
        os.system(f'mode con: cols={w} lines={h}')
    else:
        os.system(f'printf \'\033[8;{h};{w}t\'')


def getch():
    if system == 'Windows':
        return msvcrt.getch()
    else:
        return sys.stdin.read(1)


def kbhit():
    if system == 'Windows':
        return msvcrt.kbhit()
    else:
        r = select([sys.stdin], [], [], 0)
        return r[0] != []


class UnicodeSingleTable(AsciiTable):
    CHAR_F_INNER_HORIZONTAL = '─'
    CHAR_F_INNER_INTERSECT = '┼'
    CHAR_F_INNER_VERTICAL = '│'
    CHAR_F_OUTER_LEFT_INTERSECT = '├'
    CHAR_F_OUTER_LEFT_VERTICAL = '┌'
    CHAR_F_OUTER_RIGHT_INTERSECT = '┤'
    CHAR_F_OUTER_RIGHT_VERTICAL = '┐'
    CHAR_H_INNER_HORIZONTAL = '─'
    CHAR_H_INNER_INTERSECT = '┼'
    CHAR_H_INNER_VERTICAL = '│'
    CHAR_H_OUTER_LEFT_INTERSECT = '├'
    CHAR_H_OUTER_LEFT_VERTICAL = '│'
    CHAR_H_OUTER_RIGHT_INTERSECT = '┤'
    CHAR_H_OUTER_RIGHT_VERTICAL = '│'
    CHAR_INNER_HORIZONTAL = '─'
    CHAR_INNER_INTERSECT = '┼'
    CHAR_INNER_VERTICAL = '│'
    CHAR_OUTER_BOTTOM_HORIZONTAL = '─'
    CHAR_OUTER_BOTTOM_INTERSECT = '┴'
    CHAR_OUTER_BOTTOM_LEFT = '└'
    CHAR_OUTER_BOTTOM_RIGHT = '┘'
    CHAR_OUTER_LEFT_INTERSECT = '├'
    CHAR_OUTER_LEFT_VERTICAL = '│'
    CHAR_OUTER_RIGHT_INTERSECT = '┤'
    CHAR_OUTER_RIGHT_VERTICAL = '│'
    CHAR_OUTER_TOP_HORIZONTAL = '─'
    CHAR_OUTER_TOP_INTERSECT = '┬'
    CHAR_OUTER_TOP_LEFT = '┌'
    CHAR_OUTER_TOP_RIGHT = '┐'

    @property
    def table(self):
        ascii_table = super(UnicodeSingleTable, self).table
        optimized = ascii_table.replace('\033(B\033(0', '')
        return optimized
