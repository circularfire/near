#!/usr/bin/python3
import sys
import re
from collections import deque

class Term(object):
    def __init__(self, term_str):
        self.term = term_str
        self.matcher = re.compile(self.term)

class AllTerms(list):
    def add(self, term_str):
        self.append(Term(term_str))


class FileTerm(list):
    def __init__(self, term):
        self.term = term  # Term object
        self.head_index = 0

    def match(self, lineno, line):
        if re.search(self.term.matcher, line):
            self.append(lineno)

    def head(self):
        return self[self.head_index]

    def has_more(self):
        return self.head_index < len(self)


    def pop(self):
        head = self.head()
        self.head_index += 1
        return head

    def __str__(self):
        return "/{}/: {}".format(self.term.term, repr(self))


class Window(object):
    def __init__(self, start):
        self.start = start
        self.end = start + CONFIG.window_size - 1
        self.lines = []

    def extend(self, lineno):
        self.end = lineno + CONFIG.window_size - 1

    def includes(self, n):
        return self.start <= n <= self.end

    @classmethod
    def from_first_term(cls, term):
        window = None
        if term.has_more():
            first = term.pop()
            window = cls(first)
            while term.has_more():
                n = term.head()
                if window.includes(n):
                    window.extend(n)
                    term.pop()
                else:
                    break
        return window

    def fill_from_subsequent_term(self, termn):
        last_added = -1
        while termn.has_more():
            n = termn.head()
            if n < self.start:
                print("dropping term2 line {}, not in previous range".format(n))
                termn.pop()
                continue
            if self.includes(n):
                last_added = n
                print("adding term2 line {}, in range".format(n))
                termn.pop()
            elif n == last_added + 1:
                print("adding term2 line {}, just at range+1".format(n))
                self.end += 1
                last_added = n
                termn.pop
            else:
                break
        if last_added < 0:
            return False
        self.end = last_added
        return True

    def slice(self, lines):
        # note, if we do context pre/post extension, make sure it's in range of lines
        self.lines = lines[self.start:self.end+1]

    def __str__(self):
        return "({},{}) lines: {}".format(self.start, self.end, len(self.lines))


class SearchFile(object):
    def __init__(self, filename, terms):
        self.name = filename
        self.contents = []
        self.windows = []
        self.terms = []
        for term in terms:
            self.terms.append(FileTerm(term))

    def find_matches(self):
        for lineno, line in enumerate(self.contents):
            for term in self.terms:
                term.match(lineno, line)

    def window_scan(self):
        term1 = self.terms[0]
        term2 = self.terms[1]

        while True:
            window = Window.from_first_term(term1)
            if window:
                print("created window from term1: {}".format(window))
                if window.fill_from_subsequent_term(term2):
                    self.windows.append(window)
            else:
                break

    def window_fill(self):
        for window in self.windows:
            window.slice(self.contents)


    def process(self):
        try:
            with open(self.name) as f:
                self.contents = list(f)
            self.find_matches()
            for term in self.terms:
                print(str(term))

            self.window_scan()
            self.window_fill()
            for window in self.windows:
                print(str(window))
                for i, line in enumerate(window.lines):
                    sys.stdout.write("{:3}: {}".format(i+window.start, line))

        except Exception:
            raise



class AllSearchFiles(list):
    def add(self, filename, terms):
        self.append(SearchFile(filename, terms))

    def process(self):
        for file in self:
            file.process()

class Config(object):
    def __init__(self):
        self.terms = AllTerms()
        self.files = AllSearchFiles()
        self.window_size = 5


CONFIG = Config()

def go():
    if len(sys.argv) < 4:
        print("usage term1 term2 file [file...]")
        sys.exit(1)

    CONFIG.terms.add(sys.argv[1])
    CONFIG.terms.add(sys.argv[2])
    for filename in sys.argv[3:]:
        CONFIG.files.add(filename, CONFIG.terms)

    CONFIG.files.process()


if __name__ == '__main__':
    go()
