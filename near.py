#!/usr/bin/python3
import sys
import re


class Term(object):
    def __init__(self, term_str):
        self.term = term_str
        flags = 0
        if near.case_insensitive:
            flags |= re.IGNORECASE
        self.matcher = re.compile(self.term, flags)

    def found_in(self, string):
        return bool(re.search(self.matcher, string))


class AllTerms(list):
    def add(self, term_str):
        self.append(Term(term_str))


class FileTerm(list):
    def __init__(self, term):
        super(FileTerm,self).__init__()
        self.term = term  # Term object

    def match(self, lineno, line):
        if self.term.found_in(line):
            self.append(lineno)

    def __str__(self):
        return "/{}/: {}".format(self.term.term, repr(self))


class Window(object):
    def __init__(self, start):
        self.start = start
        self.end = start + near.window_size - 1
        self.lines = []

    def extend(self, lineno):
        self.end = lineno + near.window_size - 1

    def includes(self, n):
        return self.start <= n <= self.end

    def preceded_by(self, n):
        return n < self.start

    @classmethod
    def from_first_term(cls, term):
        window = None
        if term:
            window = cls(term.pop(0))
            while term and window.includes(term[0]):
                window.extend(term.pop(0))
        return window

    def fill_from_subsequent_term(self, term):
        last_added = -1
        while term:
            n = term[0]
            if self.preceded_by(n):
                # this line is before our range, possibly after some earlier range
                #print("dropping term2 line {}, not in previous range".format(n))
                term.pop(0)
                continue
            elif self.includes(n):
                # in our range, add it
                last_added = n
                #print("adding term2 line {}, in range".format(n))
                term.pop(0)
            elif n == last_added + 1:
                # elastic, stretch range to cover next line
                #print("adding term2 line {}, just at range+1".format(n))
                self.end += 1
                last_added = n
                term.pop(0)
            else:
                # nothing else (or nothing at all) in our range
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

        while term1:
            window = Window.from_first_term(term1)
            if window:
                #print("created window from term1: {}".format(window))
                if window.fill_from_subsequent_term(term2):
                    #print("term2 adjusted window: {}".format(window))
                    self.windows.append(window)

    def window_fill(self):
        for window in self.windows:
            window.slice(self.contents)

    def search(self):
        try:
            with open(self.name) as f:
                self.contents = list(f)
            self.find_matches()
#            for term in self.terms:
#                print(str(term))

            self.window_scan()
            self.window_fill()
            if self.windows:
                print(self.name)
            for window in self.windows:
                #print(str(window))
                lines_out = []
                for i, line in enumerate(window.lines):
                    lines_out.append("{:3}: {}".format(i+window.start, line))
                print("".join(lines_out)+"--------------------")

        except IOError as ioe:
            sys.stderr.write(str(ioe)+"\n")


class AllSearchFiles(list):
    def add(self, filename, terms):
        self.append(SearchFile(filename, terms))

    def search(self):
        for file in self:
            file.search()

class Near(object):
    def __init__(self):
        self.terms = AllTerms()
        self.files = AllSearchFiles()
        self.window_size = 8
        self.case_insensitive = False
        self.numbered_lines = False

    def search_all_files(self):
        self.files.search()


near = Near()

def main():
    if len(sys.argv) < 4:
        print("usage term1 term2 file [file...]")
        sys.exit(1)
    near.terms.add(sys.argv[1])
    near.terms.add(sys.argv[2])
    for filename in sys.argv[3:]:
        near.files.add(filename, near.terms)

    near.search_all_files()


if __name__ == '__main__':
    main()
