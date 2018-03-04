import sys


class Term(object):
    def __init__(self, term_str):
        self.term = term_str
        self.matcher = None # re.compile(^^)

class AllTerms(list):
    def add(self, term_str):
        self.append(Term(term_str))

class FileTerm(object):
    def __init__(self, term):
        self.term = term  # Term object
        self.lines = []


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
        with open(self.filename) as f:
            self.contents = f.read.splitlines()


class AllSearchFiles(list):
    def add(self, filename):
        self.append(SearchFile(filename))


class Config(object):
    def __init__(self):
        self.terms = AllTerms()
        self.files = AllSearchFiles()


CONFIG = Config()

def go():
    if len(sys.argv) < 4:
        printf("usage term1 term2 file [file...]")
        sys.exit(1)

    CONFIG.terms.add(sys.argv[1])
    CONFIG.terms.add(sys.argv[2])
    for filename in sys.argv[3:]:
        CONFIG.files.add(filename, CONFIG.terms)



