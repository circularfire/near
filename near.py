#!/usr/bin/python3
import sys
import re
import click

class SearchTerm(object):
    """
    A search term from the user, in regex format.
    Becomes a pre-compiled regular expression.
    """
    def __init__(self, name, term_str):
        self.name = name
        self.term_str = term_str
        flags = 0
        if app.config.case_insensitive:
            flags |= re.IGNORECASE
        self.matcher = re.compile(self.term_str, flags)

    def found_in(self, string):
        return bool(re.search(self.matcher, string))

    def __str__(self):
        return "'{}':/{}/".format(self.name, self.term_str)



class AllSearchTerms(dict):
    """
    All search terms supplied by the user.
    (currently just two, but theoretically could be any number)
    """
    def __init__(self):
        super(AllSearchTerms, self).__init__()

    def add(self, name, term_str):
        self[name] = SearchTerm(name, term_str)


class FileTermMap(list):
    """
    A map of all lines in a file which contain the search term.
    """
    def __init__(self, search_term):
        super(FileTermMap,self).__init__()
        self.search_term = search_term  # SearchTerm object

    def match(self, lineno, line):
        if self.search_term.found_in(line):
            self.append(lineno)

    def __str__(self):
        return "{}: {}".format(str(self.search_term), repr(self))


class Window(object):
    """
    A window on a range of lines in the file which contain 
    all search terms.
    """
    def __init__(self, start):
        self.start = start
        self.end = start + app.config.window_size - 1
        self.lines = []

    def extend(self, lineno):
        self.end = lineno + app.config.window_size - 1

    def includes(self, n):
        return self.start <= n <= self.end

    def preceded_by(self, n):
        return n < self.start

    @classmethod
    def from_first_term(cls, term):
        """
        Create a window starting at a line where the first
        search term was found.  
        """
        window = None
        if term:
            window = cls(term.pop(0))
            while term and window.includes(term[0]):
                # might want to limit extension to window_len * 2 or something like that
                window.extend(term.pop(0))
        return window

    def fill_from_subsequent_term(self, term):
        """
        Given a window started from the first search term,
        see if a subsequent search term is in that window.
        May possibly shorten or extend the window depending
        on the distance of the last term in that window.

        Also, drop any instances of this term which came
        before this window's start.  They aren't in this
        window or the preceding window, so no window match.

        :return: True if subsequent term found in window, False if no match
        """
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
            elif app.config.elastic and n == last_added + 1:
                # stretch range to cover next line
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
    """
    A file to be searched.
    """
    def __init__(self, filename, terms):
        self.name = filename
        self.contents = []
        self.windows = []
        self.search_terms = [FileTermMap(terms['term1']), FileTermMap(terms['term2'])]

    def find_matches(self):
        for lineno, line in enumerate(self.contents):
            for search_term in self.search_terms:
                search_term.match(lineno, line)
        #for search_term in self.search_terms:
        #    print(str(search_term))

    def window_scan(self):
        """
        Create a list of Windows which contain all search terms.
        """
        term1 = self.search_terms[0]
        term2 = self.search_terms[1]

        while term1:
            window = Window.from_first_term(term1)
            if window:
                #print("created window from term1: {}".format(window))
                if window.fill_from_subsequent_term(term2):
                    #print("term2 adjusted window: {}".format(window))
                    self.windows.append(window)

    def window_fill(self):
        """
        Once a list of windows has been identified,
        fill them in with lines from the file.
        """
        for window in self.windows:
            window.slice(self.contents)
        self.contents = []  # free up the memory

    def display_all_matches(self):
        if self.windows:
            print(self.name)
        for window in self.windows:
            #print(str(window))
            lines_out = []
            for i, line in enumerate(window.lines):
                lineno = "{:3}: ".format(i+window.start) if app.config.numbered_lines else ""
                lines_out.append(lineno + line)
            print("".join(lines_out)+"--------------------")

    def search(self):
        """
        This is the heart of the application.
        Find all search terms in the file, then chop into windows
        where the terms are 'near' each other, fill the windows.
        """
        try:
            with open(self.name) as f:
                self.contents = list(f)
            self.find_matches()
            self.window_scan()
            self.window_fill()
        except IOError as ioe:
            sys.stderr.write(str(ioe)+"\n")


class AllSearchFiles(list):
    def add(self, filename, search_terms):
        self.append(SearchFile(filename, search_terms))

    def search(self):
        for file in self:
            file.search()
            file.display_all_matches()

class Config(object):
    def __init__(self):
        self.window_size = 8
        self.case_insensitive = False
        self.numbered_lines = True
        self.blank_lines_relevant = True
        self.elastic = True

class App(object):
    def __init__(self):
        self.config = Config()
        self.search_terms = AllSearchTerms()
        self.files = AllSearchFiles()

    def search_all_files(self):
        self.files.search()


app = App()


"""

Args

two terms (optionally 3-?)
any number of files

Options

window size: int (1-?)
elastic: bool (allow expansion if term found just outside window - up to ? lines)
case insensitive (? and possibly other RE options)
line numbering


...discussion...

*
some options related to blank lines or similar breaks
akin to "paragraph" concept in text docs.  methods and
many other code blocks often end this way.  
- stop at blank line(s) (default to one, but optionally 2 or more?)
- extend window to next blank line(s)
- allow same behaviours for user-specified file delimiters, 
  perhaps a regex (using a regex to ID blank lines now anyway)

*
file tree search (later, allow pruning)



"""
DEFAULT_WINDOW_SIZE = 8

@click.command()
@click.option('--window-size', '-w', default=DEFAULT_WINDOW_SIZE,
help='window size (what is "near").')
@click.option('--elastic/--no-elastic', is_flag=True, default=True,
help='automatically extend when term found just outside window.')
@click.option('--nocase', '-i', is_flag=True, default=False,
help='ignore case.')
@click.option('--number-lines', '-nl', is_flag=True, default=False,
help='number lines.')
@click.argument('terms', nargs=2)
#@click.argument('files', type=click.File('r'), nargs=-1)
@click.argument('files', nargs=-1)
def cli(window_size, elastic, nocase, number_lines, terms, files):
    app.config.window_size = window_size
    app.config.elastic = elastic
    app.config.case_insensitive = nocase
    app.config.numbered_lines = number_lines
    app.config.blank_lines_relevant = True
    app.search_terms.add('term1', terms[0])
    app.search_terms.add('term2', terms[1])
    #if app.config.blank_lines_relevant:
    #    app.search_terms.add('blankline', r'^\s*$')
    for filename in files:
        app.files.add(filename, app.search_terms)

    app.search_all_files()


if __name__ == '__main__':
    cli()
