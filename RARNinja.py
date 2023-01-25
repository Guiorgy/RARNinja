import math
import os
import time
from itertools import islice
from multiprocessing import Pool, Manager, cpu_count
from typing import Optional, Sequence, Iterable

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
    source_length = len(source)

    if chunk_size is None:
        if chunks is None:
            raise ValueError

        chunk_size = math.floor(source_length / chunks)
        if chunk_size * chunks < source_length:
            chunk_size += 1

    for i in range(0, source_length, chunk_size):
        yield source[i:(i + chunk_size - 1)]


class DictionaryGenerator:
    def _new_state(self, start=0, stop=None):
        return islice(self._alphabet, start, stop)

    def __init__(self, alphabet: str, word_length: int, start: Optional[int] = None, stop: Optional[int] = None):
        if not alphabet:
            raise ValueError('alphabet can\'t be empty')
        if word_length < 1:
            raise ValueError('word_length has to be positive')

        self._alphabet = alphabet
        self._word_length = word_length

        alphabet_size = len(alphabet)
        dictionary_size = pow(alphabet_size, word_length)

        if start is not None and not (0 <= start < dictionary_size):
            raise ValueError(f'start needs to be between 0 and dictionary_size({dictionary_size})')
        if stop is not None and not ((start if start else 0) <= stop):
            raise ValueError(f'stop can\'t be less than start')

        if stop is None or stop >= dictionary_size:
            stop = dictionary_size - 1

        states = [None] * word_length

        if start is None or start == 0:
            word_count = 0

            states = [self._new_state() for _ in range(word_length)]

        else:
            _start = word_count = start

            i = word_length - 1

            while i >= 0 and start:
                offset = _start % alphabet_size

                states[i] = self._new_state(start=offset)

                _start -= offset
                _start = math.floor(_start / alphabet_size)

                i -= 1

            while i >= 0:
                states[i] = self._new_state()
                i -= 1

        generated_word = ''
        for i in range(self._word_length - 1):
            generated_word += next(states[i])

        self._states = states
        self._word_count = word_count
        self._stop = stop
        self._length = stop - start + 1
        self._generated_word = generated_word
        self._last_index = self._word_length - 1
        self._current_index = self._last_index

    def __next__(self):
        while True:
            if self._current_index >= 0 and self._word_count <= self._stop:
                try:
                    word = self._generated_word + next(self._states[self._last_index])
                    self._word_count += 1
                    return word
                except StopIteration:
                    self._states[self._last_index] = self._new_state()

                    word_changed_part = ''
                    self._current_index = self._last_index - 1
                    while self._current_index >= 0:
                        try:
                            word_changed_part = next(self._states[self._current_index]) + word_changed_part
                            self._generated_word = self._generated_word[
                                                   :-(self._last_index - self._current_index)] + word_changed_part
                            break
                        except StopIteration:
                            self._states[self._current_index] = self._new_state()
                            word_changed_part = next(self._states[self._current_index]) + word_changed_part
                            self._current_index -= 1
            else:
                raise StopIteration

    def __iter__(self):
        return self

    def __len__(self):
        return self._length


def dictionary_chunk_generators(alphabet: str, word_length: int, chunks: int, chunk: Optional[int] = None):
    if not (chunk is None or 0 <= chunk < chunks):
        raise ValueError

    alphabet_size = len(alphabet)
    dictionary_size = pow(alphabet_size, word_length)

    chunk_size = math.floor(dictionary_size / chunks)
    if chunk_size * chunks < dictionary_size:
        chunk_size += 1

    generators = [
        DictionaryGenerator(alphabet, word_length, chunk_start, chunk_start + chunk_size - 1)
        for i, chunk_start in enumerate(range(0, dictionary_size, chunk_size)) if chunk is None or i == chunk
    ]

    if chunk is None:
        return generators
    elif generators:
        return generators[0]
    else:
        return None


class ChainGenerator(Iterable):
    def __init__(self, generators: Sequence[DictionaryGenerator]):
        self._length = 0
        for gen in generators:
            self._length += len(gen)

        self._generators = generators
        self._index = 0
        self._stop = len(generators)

    def __next__(self):
        while True:
            try:
                return next(self._generators[self._index])
            except StopIteration:
                self._index += 1

                if self._index == self._stop:
                    raise

    def __iter__(self):
        return self

    def __len__(self):
        return self._length


def dictionary_chunk_generators_ranged_length(alphabet: str, min_word_length: int, max_word_length: int, chunks: int, chunk: Optional[int] = None):
    if max_word_length < min_word_length:
        raise ValueError
    if not (chunk is None or 0 <= chunk < chunks):
        raise ValueError

    generators = [[] for _ in range(chunks)]

    for word_length in range(min_word_length, max_word_length + 1):
        gens = dictionary_chunk_generators(alphabet, word_length, chunks, chunk)

        if chunk is None:
            for i in range(len(gens)):
                if gens[i]:
                    generators[i].append(gens[i])
        elif gens:
            generators[chunk].append(gens)

    if chunk is None:
        return [ChainGenerator(gen) for gen in generators]
    else:
        return ChainGenerator(generators[chunk])


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
        stop_event = manager.Event()

        if dictionary:
            args = [(RAR, chunk, stop_event, showProgress, thread) for thread, chunk in enumerate(chunkify(dictionary, chunks=threads)) if chunk]
        else:
            generators = dictionary_chunk_generators_ranged_length(alphabet, min_len, max_len, threads)
            args = [(RAR, generators[thread], stop_event, showProgress, thread) for thread in range(threads)]

        with Pool(len(args)) as pool:
            # TODO: handle CTRL^C termination
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

        if completionTime != 0:
            rate = (int(tries) // completionTime)
            print(f'\n\nThe task completed in {round(completionTime)} seconds. (at ~{rate} tries/sec)')

    print('Press any key to exit.')
    input()
