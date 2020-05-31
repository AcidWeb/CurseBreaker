import os
import sys
import platform

system = platform.system()

if system == 'Windows':
    import msvcrt
else:
    from select import select


def pause(headless):
    if headless:
        return
    elif system == 'Windows':
        os.system('pause')
    else:
        os.system('/bin/bash -c "read -rsp $\'Press any key to continue . . .\n\' -n 1"')


def timeout(headless):
    if headless:
        return
    elif system == 'Windows':
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
