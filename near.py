"""
A utility to find search terms within a specfied line window.
"""
from __future__ import print_function
import sys
import re
from bisect import bisect_left
import click


DEFAULT_WINDOW_SIZE = 8



class SearchTerm(object):
    """
    A search term from the user, in regex format.
    Becomes a pre-compiled regular expression.
    """
    def __init__(self, term_str):
        self.term_str = term_str
        flags = 0
        if app.config.case_insensitive:
            flags |= re.IGNORECASE
        self.matcher = re.compile(self.term_str, flags)

    def found_in(self, string):
        return bool(re.search(self.matcher, string))

    def __str__(self):
        return "/{}/".format(self.term_str)


class AllSearchTerms(list):
    """
    All search terms supplied by the user.
    """
    def __init__(self):
        super(AllSearchTerms, self).__init__()

    def add(self, term_str):
        self.append(SearchTerm(term_str))


class Window(object):
    """
    A window on a range of lines in the file which contain 
    all search terms.
    """
    def __init__(self, lineno, end=None):
        self.start = lineno
        self.end = end if end else lineno + app.config.window_size
        self.has_match = False
        self.lines = []

    def extend(self, lineno):
        self.end = lineno + app.config.window_size

    def includes(self, lineno):
        return self.start <= lineno <= self.end

    # TODO: need some sort of AND/OR operators to control how merged
    def merge(self, other):
        self.end = max(self.end, other.end)
        if other.has_match:
            self.has_match = True

    def dup(self):
        return Window(self.start, self.end)

    def capture(self, lines):
        # note, if we do context pre/post extension, make sure it's in range of lines
        self.lines = lines[self.start:self.end+1]

    def __str__(self):
        return "({},{}) lines: {}".format(self.start, self.end, len(self.lines))


class TermLineMap(list):
    """
    A map of all lines in a file which contain the search term.

    This list is naturally sorted on creation. 
    """
    def __init__(self, search_term):
        super(TermLineMap,self).__init__()
        self.search_term = search_term  # SearchTerm object

    def match_line(self, lineno, line):
        if self.search_term.found_in(line):
            self.append(lineno)

    def at_or_after(self, start):
        return self[bisect_left(self, start):]

    def candidates(self):
        """
        Generate candidate windows starting at a line containing 
        the first search term.

        It empties itself as it generates windows.
        """
        while self:
            window = Window(self.pop(0))
            while self and window.includes(self[0]):
                # might want to limit extension to window_len * 2 or something like that
                window.extend(self.pop(0))
            yield window

    def match(self, candidate):
        """
        Given a window started from the first search term,
        see if this search term is in that window.

        """
        last_added = (-2)
        window = candidate.dup()
        for lineno in self.at_or_after(window.start):
            if window.includes(lineno):
                # in our range, add it
                last_added = lineno
                #print("adding term line {}, in range".format(lineno))
            elif  lineno == (last_added + 1) and app.config.elastic:
                # stretch range to cover next line
                #print("adding term line {}, just at range+1".format(lineno))
                window.end += 1
                last_added = lineno
            else:
                # nothing else (or nothing at all) in our range
                break
        if last_added >= 0:
            window.length = last_added
            window.has_match = True
        return window

    def __str__(self):
        return "{}: {}".format(str(self.search_term), repr(self))


class SearchFile(object):
    """
    A file to be searched.
    """
    def __init__(self, filename, terms):
        self.name = filename
        self.contents = []
        self.windows = []
        self.term_linemaps = [TermLineMap(term) for term in terms]

    def create_linemaps_for_terms(self):
        for lineno, line in enumerate(self.contents):
            for term in self.term_linemaps:
                term.match_line(lineno, line)
        #for term in self.term_linemaps:
        #    print(str(term))

    def scan_linemaps_for_window_matches(self):
        """
        Create a list of Windows which contain all search terms.
        """
        first_term = self.term_linemaps[0]
        for window in first_term.candidates():
            #print("created a window from first term: {}".format(window))
            result = window.dup()
            for term in self.term_linemaps[1:]:
                result.merge( term.match(window) )
            if result.has_match:
                #print("subsequent term adjusted window: {}".format(result))
                self.windows.append(result)

    def load_windows(self):
        """
        Once a list of windows has been identified,
        fill them in with lines from the file.
        """
        for window in self.windows:
            window.capture(self.contents)
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
        This is the heart of the application - 
        Find all search terms in the file.
        Chop into windows where the terms are 'near' each other.
        Load text into windows.
        Ready to display.
        """
        try:
            with open(self.name) as f:
                self.contents = list(f)
            self.create_linemaps_for_terms()
            self.scan_linemaps_for_window_matches()
            self.load_windows()
        except IOError as ioe:
            sys.stderr.write(str(ioe)+"\n")


class AllSearchFiles(list):
    def add(self, filename, terms):
        self.append(SearchFile(filename, terms))

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
        self.terms = AllSearchTerms()
        self.files = AllSearchFiles()

    def search_all_files(self):
        self.files.search()


app = App()


"""
two terms (optionally 3-?)
any number of files

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
allow pre/post window lines for context (like grep -A -B but easier)

*
file tree search (later, allow pruning)

"""

@click.command()
@click.option('--distance', '-l', default=DEFAULT_WINDOW_SIZE,
help='range of lines to consider "near".')
@click.option('--elastic/--no-elastic', is_flag=True, default=True,
help='automatically extend when term found just outside range.')
@click.option('--nocase', '-i', is_flag=True, default=False,
help='ignore case.')
@click.option('--number-lines', '-nl', is_flag=True, default=False,
help='show line numbers.')
@click.argument('terms', nargs=2)
# TODO: modify classes to accept a click.File instead of filename
#@click.argument('files', type=click.File('r'), nargs=-1)
@click.argument('files', nargs=-1)
def cli(distance, elastic, nocase, number_lines, terms, files):
    """
    Find two* search terms which are within a certain
    number of lines of each other. 
    

    * may allow more than two search terms in future
    """
    app.config.window_size = distance
    app.config.elastic = elastic
    app.config.case_insensitive = nocase
    app.config.numbered_lines = number_lines
    app.config.blank_lines_relevant = True
    app.terms.add(terms[0])
    app.terms.add(terms[1])
    #if app.config.blank_lines_relevant:
    #    app.term_linemaps.add('blankline', r'^\s*$')
    for filename in files:
        app.files.add(filename, app.terms)

    app.search_all_files()


if __name__ == '__main__':
    cli()

