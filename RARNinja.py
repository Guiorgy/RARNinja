import math
import os
import time
from itertools import product
from multiprocessing import Pool, Manager, cpu_count

import colorama
import rarfile
from termcolor import colored

colorama.init()

rarfile.UNRAR_TOOL = 'UnRAR.exe'

BANNER = [
    colored('''
   ██▀███   ▄▄▄       ██▀███   ███▄    █  ██▓ ███▄    █  ▄▄▄██▀▀▀▄▄▄
  ▓██ ▒ ██▒▒████▄    ▓██ ▒ ██▒ ██ ▀█   █ ▓██▒ ██ ▀█   █    ▒██  ▒████▄
  ▓██ ░▄█ ▒▒██  ▀█▄  ▓██ ░▄█ ▒▓██  ▀█ ██▒▒██▒▓██  ▀█ ██▒   ░██  ▒██  ▀█▄
  ▒██▀▀█▄  ░██▄▄▄▄██ ▒██▀▀█▄  ▓██▒  ▐▌██▒░██░▓██▒  ▐▌██▒▓██▄██▓ ░██▄▄▄▄██
  ░██▓ ▒██▒ ▓█   ▓██▒░██▓ ▒██▒▒██░   ▓██░░██░▒██░   ▓██░ ▓███▒   ▓█   ▓██▒
  ░ ▒▓ ░▒▓░ ▒▒   ▓▒█░░ ▒▓ ░▒▓░░ ▒░   ▒ ▒ ░▓  ░ ▒░   ▒ ▒  ▒▓▒▒░   ▒▒   ▓▒█░
    ░▒ ░ ▒░  ▒   ▒▒ ░  ░▒ ░ ▒░░ ░░   ░ ▒░ ▒ ░░ ░░   ░ ▒░ ▒ ░▒░    ▒   ▒▒ ░
    ░░   ░   ░   ▒     ░░   ░    ░   ░ ░  ▒ ░   ░   ░ ░  ░ ░ ░    ░   ▒
     ░           ░  ░   ░              ░  ░           ░  ░   ░        ░  ░''', 'blue'),
    colored('''             -------------------------------------------------''', 'blue'),
    colored('''             || RARNinja: The RAR Password Cracking Utility ||''', 'red'),
    colored('''             -------------------------------------------------''', 'blue'),
]


def print_banner():
    for banner in BANNER:
        print(banner)


def count_lines(file_path, encoding='utf-8'):
    def blocks(file, size=65536):
        while True:
            b = file.read(size)
            if not b: break
            yield b

    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
        return sum(bl.count('\n') for bl in blocks(f))


def chunkify(source, *, chunk_size=None, chunks=None):
    if chunk_size is None:
        if chunks is None:
            raise ValueError

        chunk_size = math.floor(len(source) / chunks)
        if chunk_size * chunks < len(source):
            chunk_size += 1

    for i in range(0, len(source), chunk_size):
        yield source[i:(i + chunk_size - 1)]


def dictionary_crack(RAR, dictionary, stop_event, progress=False, thread=0):
    correct_password = None
    
    if progress:
        lines = len(dictionary)
        skip = max(1, math.floor(lines / 100))
        skipped = skip - 1

    with rarfile.RarFile(RAR, 'r') as rar:
        for tries, password in enumerate(dictionary):
            if stop_event.is_set():
                break

            if progress:
                skipped += 1
                if skipped == skip:
                    skipped = 0
                    percent = round(tries / lines * 100, 1)
                    print(f'[{thread}] Progress: {percent}%')

            try:
                rar.extractall(path='./Extracted/', pwd=password)
                print(colored(f'\n[{thread}] Cracked and extracted! Password: {password}', 'green'))
                correct_password = password
                stop_event.set()
                break

            except:
                pass

    if progress and correct_password is None:
        print(f'[{thread}] Progress: 100.0%')

    return correct_password, tries


def _clear_screen_posix():
    _ = os.system('clear')


def _clear_screen_win():
    _ = os.system('cls')


def clear_screen():
    clear_screen.clear()
    print_banner()


if os.name == 'posix':
    clear_screen.clear = _clear_screen_posix

else:
    clear_screen.clear = _clear_screen_win


if __name__ == '__main__':

    print_banner()

    RAR = None
    while RAR is None:
        RAR = input('\nEnter RAR file path: ').strip()

        if not os.path.isfile(RAR):
            clear_screen()
            print('\nEither file does not exist or invalid path entered. Try again.\n')
            RAR = None

    dictionary = None
    while dictionary is None:
        print('\nUse dictionary?')
        dicPrompt = input('1. Yes\n2. No\n(Default: No)\n').strip()

        if dicPrompt in ['1', 'y', 'Y', 'yes', 'Yes', 'YES']:
            while dictionary is None:
                dictionary = input('Enter dictionary file path: ').strip()

                if not os.path.isfile(dictionary):
                    clear_screen()
                    print('\nEither file does not exist or invalid path entered. Try again.\n')
                    dictionary = None

        elif dicPrompt in ['', '0', 'n', 'N', 'no', 'No', 'NO']:
            dictionary = False

        else:
            clear_screen()
            print('\nInvalid entry. Try again.\n')

    if dictionary:
        with open(dictionary, 'r') as file:
            dictionary = [line.strip() for line in file.readlines()]

    else:
        min_len = None
        while min_len is None:
            min_len = input('\nEnter the minimum password length: ').strip()

            try:
                min_len = int(min_len)

                if min_len < 1:
                    clear_screen()
                    print('\nOut of range. Try again.\n')
                    threads = None

            except:
                clear_screen()
                print('\nInvalid format. Try again.\n')
                min_len = None

        max_len = None
        while max_len is None:
            max_len = input('\nEnter the maximum password length: ').strip()

            try:
                max_len = int(max_len)

                if max_len < 1:
                    clear_screen()
                    print('\nOut of range. Try again.\n')
                    threads = None

            except:
                clear_screen()
                print('\nInvalid format. Try again.\n')
                max_len = None

        alphabet = None
        while alphabet is None:
            useNumbers = None
            while useNumbers is None:
                print('\nUse numbers? (0-9)')
                numPrompt = input('1. Yes\n2. No\n(Default: Yes)\n').strip()

                if numPrompt in ['', '1', 'y', 'Y', 'yes', 'Yes', 'YES']:
                    useNumbers = True

                elif numPrompt in ['0', 'n', 'N', 'no', 'No', 'NO']:
                    useNumbers = False

                else:
                    clear_screen()
                    print('\nInvalid entry. Try again.\n')

            useLetters = None
            while useLetters is None:
                print('\nUse English letters? (a-z, A-Z)')
                letterPrompt = input('1. Yes\n2. No\n(Default: Yes)\n').strip()

                if letterPrompt in ['', '1', 'y', 'Y', 'yes', 'Yes', 'YES']:
                    useLetters = True

                elif letterPrompt in ['0', 'n', 'N', 'no', 'No', 'NO']:
                    useLetters = False

                else:
                    clear_screen()
                    print('\nInvalid entry. Try again.\n')

            useSymbols = None
            while useSymbols is None:
                print('\nUse symbols? ( !"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~)')
                symsPrompt = input('1. Yes\n2. No\n(Default: Yes)\n').strip()

                if symsPrompt in ['', '1', 'y', 'Y', 'yes', 'Yes', 'YES']:
                    useSymbols = True

                elif symsPrompt in ['0', 'n', 'N', 'no', 'No', 'NO']:
                    useSymbols = False

                else:
                    clear_screen()
                    print('\nInvalid entry. Try again.\n')

            customChars = None
            while customChars is None:
                print('\nUse custom characters? (You\'ll enter them next)')
                charsPrompt = input('1. Yes\n2. No\n(Default: No)\n').strip()

                if charsPrompt in ['1', 'y', 'Y', 'yes', 'Yes', 'YES']:
                    customChars = input('\nEnter the custom characters (in a single line): ')
                    customChars = set(*customChars)

                elif charsPrompt in ['', '0', 'n', 'N', 'no', 'No', 'NO']:
                    customChars = False

                else:
                    clear_screen()
                    print('\nInvalid entry. Try again.\n')

            alphabet = []

            if useNumbers:
                alphabet += [chr(i) for i in range(48, 58)]

            if useLetters:
                alphabet += [chr(i) for i in range(65, 91)] + [chr(i) for i in range(97, 123)]

            if useSymbols:
                alphabet += [chr(i) for i in range(32, 48)] + [chr(i) for i in range(58, 65)] + [chr(i) for i in range(91, 97)] + [chr(i) for i in range(123, 127)]

            if customChars:
                alphabet += customChars

            if not alphabet:
                clear_screen()
                print('\nThe character set can\'t be empty. Try again.\n')
                alphabet = None

        dictionary = []
        for i in range(min_len, max_len + 1):
            dictionary += [''.join(t) for t in product(alphabet, repeat=i)]

    showProgress = None
    while showProgress is None:
        print('\nShow progress?')
        progressPrompt = input('1. Yes (slower)\n2. No (faster)\n(Default: No)\n').strip()

        if progressPrompt in ['1', 'y', 'Y', 'yes', 'Yes', 'YES']:
            showProgress = True

        elif progressPrompt in ['', '0', 'n', 'N', 'no', 'No', 'NO']:
            showProgress = False

        else:
            clear_screen()
            print('\nInvalid entry. Try again.\n')

    max_threads = cpu_count()
    def_threads = max(1, max_threads - 2)
    threads = None
    while threads is None:
        threads = input(f'\nEnter number of parallel threads (Max: {max_threads}, Default: {def_threads}): ').strip()

        try:
            threads = def_threads if not threads else int(threads)

            if 1 > threads > max_threads:
                clear_screen()
                print('\nOut of range. Try again.\n')
                threads = None

        except:
            clear_screen()
            print('\nInvalid format. Try again.\n')
            threads = None

    correct_password = None
    tries = 0
    clear_screen()
    with Manager() as manager:
        with Pool(threads) as pool:
            # TODO: handle CTRL^C termination
            stop_event = manager.Event()
            args = [(RAR, chunk, stop_event, showProgress, i) for i, chunk in enumerate(chunkify(dictionary, chunks=threads))]

            start = time.time()
            for password, _tries in pool.starmap(dictionary_crack, args):
                if password:
                    correct_password = password

                tries += _tries
            completionTime = time.time() - start

    if correct_password:
        if completionTime == 0:
            print('\n\nThe task completed successfully.')

        else:
            rate = (int(tries) // completionTime)
            print(f'\n\nThe task completed successfully in {round(completionTime)} seconds. (at ~{rate} tries/sec)')

    else:
        print(colored('Cracking of the password was unsuccessful', 'red'))

    print('Press any key to exit.')
    input()
