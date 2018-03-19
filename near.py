"""
A utility to find search terms within a specfied line window.
"""
from __future__ import print_function
import sys
import re
import click


DEFAULT_WINDOW_SIZE = 8

NO_BORDER, EXTEND_TO_BORDER, TRUNCATE_AT_BORDER = range(3)
# matches a blank line  (default border)
BLANK_LINE_TERM = r'^\s*$'


class SearchTerm(object):
    """
    A search term from the user, in regex format.
    Becomes a pre-compiled regular expression.
    """
    def __init__(self, term_str):
        self.term_str = term_str
        self.is_first = False
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
    def add(self, term_str):
        term = SearchTerm(term_str)
        if len(self) == 0:
            term.is_first = True
        self.append(term)


class Window(object):
    """
    A window on a range of lines in the file. It's expected
    to contain lines containing the initial search term,
    and lines with other search terms which are "near". 
    """
    def __init__(self):
        self.start = 0
        self.end = 0
        self.limit = 0
        self.terms = set()
        self.lines = []

    def add_in_range(self, lineno, matched_terms):
        """
        If line is in range, add to this window, 
        otherwise return False.
        Also, track the terms which matched. This window
        won't be valid unless it contains lines which 
        matched at least two terms.

        lineno: index of line which matched one (or more) terms
        terms: set of terms whic matched this line
        return: True if line added to window, False if out of range
        """
        if self.is_empty:
            self.start = lineno
            self.limit = lineno + app.config.window_size
        else:
            if app.config.elastic and lineno == self.limit+1:
                self.limit += 1
            if lineno > self.limit:
                return False
        self.end = lineno
        self.terms.update(matched_terms)
        return True

    @property
    def is_empty(self):
        return len(self.terms) == 0

    @property
    def is_valid(self):
        return len(self.terms) > 1

    def capture(self, lines):
        # note, if we do context pre/post extension, make sure it's in range of lines
        self.lines = lines[self.start:self.end+1]

    def __str__(self):
        return "(terms:{}) {},{}".format(len(self.terms), self.start, self.end)


class SearchFile(object):
    """
    A file to be searched.
    """
    def __init__(self, filename, all_terms):
        self.name = filename
        self.contents = []
        self.windows = []
        self.terms = all_terms

    def match_windows(self):
        """
        Scan all lines in the file, generate match windows
        containing search terms found near each other.
        """
        window = Window()
        for lineno, line in enumerate(self.contents):
            matched_terms = [term for term in self.terms if term.found_in(line)]
            if len(matched_terms) == 0:
                continue  # no match: next!
            first_term_found = any(term.is_first for term in matched_terms)
            if app.config.ordered and window.is_empty and not first_term_found:
                continue  # ordered: only start a window with first term
            if not window.add_in_range(lineno, matched_terms):
                # This line number is out of current window's range
                # if window contains good matches, emit it; if not, discard
                if window.is_valid:
                    window.capture(self.contents)
                    yield window
                # start new window, and add this line if allowed
                window = Window()
                if (not app.config.ordered) or first_term_found:
                    window.add_in_range(lineno, matched_terms)
        if window.is_valid:
            # final window has valid matches, emit it
            window.capture(self.contents)
            yield window
        self.contents = [] # no longer needed

    def display_all_matches(self):
        if self.windows and len(app.files) > 1:
            print(self.name)
        for window in self.windows:
            lines_out = []
            if app.config.numbered_lines:
                for i, line in enumerate(window.lines):
                    lines_out.append("{:3}: {}".format(i+window.start, line))
            else:
                lines_out = window.lines
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
            for window in self.match_windows():
                self.windows.append(window)
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
        self.ordered = True
        self.numbered_lines = True
        self.border_action = NO_BORDER
        self.elastic = True


class App(object):
    def __init__(self):
        self.config = Config()
        self.terms = AllSearchTerms()
        self.files = AllSearchFiles()


app = App()


"""
...discussion...

*
some options related to blank lines or similar breaks
akin to "paragraph" concept in text docs.  methods and
many other code blocks often end this way.  
- stop at blank line(s) (default to one, but optionally 2 or more?)
- extend window to next blank line(s)
- allow same behaviours for user-specified file delimiters, 
  perhaps a regex (default regex is blank lines now, could be specified)

*
allow pre/post window lines for context (like grep -A -B but easier)

*
file tree search (later, allow pruning)
"""

@click.command()
@click.option('--distance', '-l', default=DEFAULT_WINDOW_SIZE,
help='range of lines to consider "near".')
@click.option('--or', 'additional_terms', multiple=True,
help='additional search term to match')
@click.option('--elastic/--no-elastic', is_flag=True, default=True,
help='automatically extend when term found just outside range.')
@click.option('--nocase', '-i', is_flag=True, default=False,
help='ignore case.')
@click.option('--ordered/--no-ordered', is_flag=True, default=True,
help='range normally starts with first term, unordered starts with any term.')
@click.option('--number-lines', '-nl', is_flag=True, default=False,
help='show line numbers.')
@click.argument('terms', nargs=2)
@click.argument('files', nargs=-1)
def cli(distance, additional_terms, elastic, nocase, ordered, number_lines, terms, files):
    """
    Find search terms which are within a certain number of lines 
    of each other. Two terms are required, and both must be present
    within that distance. This match is 'term1 AND term2'.
    Additional terms may be supplied with "--or term".
    In this case, it will be 'term1 AND (term2 OR term3 OR ...)'
    By default, the matched range must start with term1. This is
    'ordered' match. Specifying --no-ordered means that a match
    range can start with any term.

    Search terms are regular expressions.  
    

    """
    app.config.window_size = distance
    app.config.elastic = elastic
    app.config.case_insensitive = nocase
    app.config.ordered = ordered
    app.config.numbered_lines = number_lines
    #app.config.border_action = NO_BORDER  # TODO: add click options for this

    for term in terms:
        app.terms.add(term)
    for term in additional_terms:
        app.terms.add(term)
    for filename in files:
        app.files.add(filename, app.terms)

    app.files.search()


if __name__ == '__main__':
    cli()

