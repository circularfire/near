"""
A utility to find search terms within a specfied line window.
"""
from __future__ import print_function
import sys
import re
from bisect import bisect_left
import click


DEFAULT_WINDOW_SIZE = 8

AND_MATCH, OR_MATCH = range(2)
NO_BORDER, EXTEND_TO_BORDER, TRUNCATE_AT_BORDER = range(3)
# matches a blank line
BLANK_LINE_TERM = r'^\s*$'


class SearchTerm(object):
    """
    A search term from the user, in regex format.
    Becomes a pre-compiled regular expression.
    """
    def __init__(self, term_str, operation=AND_MATCH):
        self.term_str = term_str
        self.operation = operation
        flags = 0
        if app.config.case_insensitive:
            flags |= re.IGNORECASE
        self.matcher = re.compile(self.term_str, flags)

    def found_in(self, string):
        return bool(re.search(self.matcher, string))

    def __str__(self):
        return "/{}/".format(self.term_str)


class AllSearchTerms(object):
    """
    All search terms supplied by the user.
    """
    def __init__(self):
        self.terms = []
        self.border = None

    def add(self, term_str, operation=AND_MATCH):
        self.terms.append(SearchTerm(term_str, operation))

    def set_border(self, border_str=BLANK_LINE_TERM):
        self.border = SearchTerm(border_str)


class Window(object):
    """
    A window on a range of lines in the file. It's expected
    to contain lines containing the initial search term,
    and lines with other search terms which are "near". 
    """
    def __init__(self, lineno, end=None, match=False):
        self.start = lineno
        self.end = end if end else lineno + app.config.window_size
        self.has_match = match
        self.lines = []

    def extend(self, lineno):
        self.end = lineno + app.config.window_size

    def includes(self, lineno):
        return self.start <= lineno <= self.end

    def merge(self, other, operation):
        # TODO: feels like min/max behavior should depend on and/or
        if other.has_match:
            self.end = min(self.end, other.end)
        if operation == AND_MATCH:
            self.has_match = self.has_match and other.has_match
        else:
            self.has_match = self.has_match or other.has_match

    def dup(self):
        return Window(self.start, self.end, match=self.has_match)

    def capture(self, lines):
        # note, if we do context pre/post extension, make sure it's in range of lines
        self.lines = lines[self.start:self.end+1]

    def __str__(self):
        return "({},{}) lines: {}".format(self.start, self.end, len(self.lines))


class TermLineMap(list):
    """
    A map of all line numbers in a file which contain the search term.

    This list is naturally ordered by the fact that line numbers
    are added during a sequential scan of the file.  As an ordered
    list it can be binary-searched.
    """
    def __init__(self, search_term):
        super(TermLineMap,self).__init__()
        self.search_term = search_term  # SearchTerm object

    def match_line(self, lineno, line):
        if self.search_term.found_in(line):
            self.append(lineno)

    def at_or_after(self, start):
        """
        List of all line numbers at or after the start line number.
        """
        # do binary search to find start of range
        return self[bisect_left(self, start):]

    def candidates(self, border_linemap=None):
        """
        Generate candidate windows starting at a line containing 
        the first search term.

        It empties itself as it generates windows.
        """
        while self:
            window = Window(self.pop(0))
            if border_linemap:
                # TODO: if truncating at border, or extending to border,
                # this seems like the place to do it.
                pass
            while self and window.includes(self[0]):
                # TODO: might want to limit extension to window_len * 2 
                # or something like that
                window.extend(self.pop(0))
            # of course it has a match - wouldn't exist otherwise
            window.has_match = True  
            yield window

    def match(self, candidate):
        """
        Given a window started from the first search term,
        see if this search term is in that window.
        """
        window = candidate.dup()
        window.has_match = False
        last_added = (-2)
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
            window.end = last_added
            window.has_match = True
        return window

    def __str__(self):
        return "{}: {}".format(str(self.search_term), repr(self))


class SearchFile(object):
    """
    A file to be searched.
    """
    def __init__(self, filename, all_terms):
        self.name = filename
        self.contents = []
        self.windows = []
        self.term_linemaps = [TermLineMap(term) for term in all_terms.terms]
        self.border_linemap = TermLineMap(all_terms.border) if all_terms.border else None

    def create_linemaps_for_terms(self):
        for lineno, line in enumerate(self.contents):
            for term in self.term_linemaps:
                term.match_line(lineno, line)
                #    print(str(term))
            if self.border_term:
                border_term.match_line(lineno, line)
                #    print(str(border_term))

    def scan_linemaps_for_window_matches(self):
        """
        Create a list of Windows which contain all search terms.
        """
        first_term = self.term_linemaps[0]
        for window in first_term.candidates():
            #print("created a window from first term: {}".format(window))
            result = window.dup()
            for term in self.term_linemaps[1:]:
                result.merge( term.match(window), term.search_term.operation )
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
        self.border_action = NO_BORDER
        self.elastic = True


class App(object):
    def __init__(self):
        self.config = Config()
        self.terms = AllSearchTerms()
        self.files = AllSearchFiles()


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
@click.option('--and', 'and_match', multiple=True,
help='additional -required- search term to match')
@click.option('--or', 'or_match', multiple=True, 
help='additional -optional- search term to match')
@click.option('--elastic/--no-elastic', is_flag=True, default=True,
help='automatically extend when term found just outside range.')
@click.option('--nocase', '-i', is_flag=True, default=False,
help='ignore case.')
@click.option('--number-lines', '-nl', is_flag=True, default=False,
help='show line numbers.')
@click.argument('terms', nargs=2)
@click.argument('files', nargs=-1)
def cli(distance, and_match, or_match, elastic, nocase, number_lines, terms, files):
    """
    Find search terms which are within a certain number of lines 
    of each other. Two terms are required, and both must be present
    within that distance. This match is 'term1 AND term2'.
    Additional terms may be supplied with "--and term" / "--or term".

    Search terms are regular expressions.  
    

    """
    app.config.window_size = distance
    app.config.elastic = elastic
    app.config.case_insensitive = nocase
    app.config.numbered_lines = number_lines
    #app.config.border_action = NO_BORDER
    app.terms.add(terms[0])
    app.terms.add(terms[1], operation=AND_MATCH)
    for term in and_match:
        app.terms.add(term, operation=AND_MATCH)
    for term in or_match:
        app.terms.add(term, operation=OR_MATCH)
    for filename in files:
        app.files.add(filename, app.terms)

    app.files.search()


if __name__ == '__main__':
    cli()

