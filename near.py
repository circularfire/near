#!/usr/bin/python3
import sys
import re

class Term(object):
    def __init__(self, term_str):
        self.term = term_str
        self.matcher = re.compile(self.term)

class AllTerms(list):
    def add(self, term_str):
        self.append(Term(term_str))

class FileTerm(object):
    def __init__(self, term):
        self.term = term  # Term object
        self.lines = []

    def match(self, lineno, line):
        if re.search(self.term.matcher, line):
            self.lines.append(lineno)

    def __str__(self):
        return "/{}/: {}".format(self.term.term, repr(self.lines))

class Window(object):
    def __init__(self):
        self.start = 0
        self.end = 0

class SearchFile(object):
    def __init__(self, filename, terms):
        self.name = filename
        self.contents = []
        self.windows = []
        self.terms = []
        for term in terms:
            self.terms.append(FileTerm(term))

    def process(self):
        with open(self.name) as f:
            self.contents = list(f)
        for lineno, line in enumerate(self.contents):
            for term in self.terms:
                term.match(lineno, line)

        for term in self.terms:
            print(str(term))


class AllSearchFiles(list):
    def add(self, filename, terms):
        self.append(SearchFile(filename, terms))


class Config(object):
    def __init__(self):
        self.terms = AllTerms()
        self.files = AllSearchFiles()


CONFIG = Config()

def go():
    if len(sys.argv) < 4:
        print("usage term1 term2 file [file...]")
        sys.exit(1)

    CONFIG.terms.add(sys.argv[1])
    CONFIG.terms.add(sys.argv[2])
    for filename in sys.argv[3:]:
        CONFIG.files.add(filename, CONFIG.terms)

    for file in CONFIG.files:
        file.process()



if __name__ == '__main__':
    go()
