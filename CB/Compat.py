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
        return msvcrt.getch() if system == 'Windows' else sys.stdin.read(1)

    def kbhit(self):
        if system == 'Windows':
            return msvcrt.kbhit()
        dr, dw, de = select([sys.stdin], [], [], 0)
        return dr != []


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
