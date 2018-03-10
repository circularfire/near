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


class TermLineMap(list):
    """
    A map of all lines in a file which contain the search term.

    This list is naturally sorted on creation. 
    """
    def __init__(self, search_term):
        super(TermLineMap,self).__init__()
        self.search_term = search_term  # SearchTerm object

    def match(self, lineno, line):
        if self.search_term.found_in(line):
            self.append(lineno)

    def at_or_after(self, start):
        return self[bisect_left(self, start):]

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
        self.has_match = False
        self.lines = []

    def extend(self, lineno):
        self.end = lineno + app.config.window_size - 1

    def includes(self, n):
        return self.start <= n <= self.end

    def preceded_by(self, n):
        return n < self.start

    @classmethod
    def from_first_term(cls, linemap):
        """
        Create a window starting at a line where the first
        search term was found.  
        """
        if not linemap:
            return None
        window = cls(linemap.pop(0))
        while linemap and window.includes(linemap[0]):
            # might want to limit extension to window_len * 2 or something like that
            window.extend(linemap.pop(0))
        return window

    def match_subsequent_term(self, linemap):
        """
        Given a window started from the first search term,
        see if a subsequent search term is in that window.
        May possibly shorten or extend the window depending
        on the distance of the last term in that window.

        """
        last_added = (-2)
        for lineno in linemap.at_or_after(self.start):
            if self.includes(lineno):
                # in our range, add it
                last_added = lineno
                #print("adding term2 line {}, in range".format(lineno))
            elif  lineno == (last_added + 1) and app.config.elastic:
                # stretch range to cover next line
                #print("adding term2 line {}, just at range+1".format(lineno))
                self.end += 1
                last_added = lineno
            else:
                # nothing else (or nothing at all) in our range
                break
        if last_added >= 0:
            if self.has_match:  
                # earlier call with another term matched
                self.end = max(self.end, last_added)
            else:
                self.end = last_added
                self.has_match = True

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
        self.term_linemaps = [TermLineMap(terms['term1']), TermLineMap(terms['term2'])]

    def find_matches(self):
        for lineno, line in enumerate(self.contents):
            for term_linemap in self.term_linemaps:
                term_linemap.match(lineno, line)
        #for term_linemap in self.term_linemaps:
        #    print(str(term_linemap))

    def window_scan(self):
        """
        Create a list of Windows which contain all search terms.
        """
        first_term_linemap = self.term_linemaps[0]
        while first_term_linemap:
            window = Window.from_first_term(first_term_linemap)
            if window:
                #print("created window from first term: {}".format(window))
                for term_linemap in self.term_linemaps[1:]:
                    window.match_subsequent_term(term_linemap)
                if window.has_match:
                    #print("subsequent term adjusted window: {}".format(window))
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
    def add(self, filename, term_linemaps):
        self.append(SearchFile(filename, term_linemaps))

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
        self.term_linemaps = AllSearchTerms()
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
    app.term_linemaps.add('term1', terms[0])
    app.term_linemaps.add('term2', terms[1])
    #if app.config.blank_lines_relevant:
    #    app.term_linemaps.add('blankline', r'^\s*$')
    for filename in files:
        app.files.add(filename, app.term_linemaps)

    app.search_all_files()


if __name__ == '__main__':
    cli()

