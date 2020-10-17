import os
import platform

system = platform.system()

if system == 'Windows':
    import msvcrt
else:
    import sys
    import termios
    import atexit
    from select import select


class KBHit:
    def __init__(self):
        if system != 'Windows':
            self.fd = sys.stdin.fileno()
            self.new_term = termios.tcgetattr(self.fd)
            self.old_term = termios.tcgetattr(self.fd)
            self.new_term[3] = (self.new_term[3] & ~termios.ICANON & ~termios.ECHO)
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new_term)
            atexit.register(self.set_normal_term)

    def set_normal_term(self):
        if system != 'Windows':
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)

    def getch(self):
        if system == 'Windows':
            return msvcrt.getch()
        else:
            return sys.stdin.read(1)

    def kbhit(self):
        if system == 'Windows':
            return msvcrt.kbhit()
        else:
            dr, dw, de = select([sys.stdin], [], [], 0)
            return dr != []


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
