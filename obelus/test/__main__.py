import os
import sys
import unittest

import obelus.test
from . import main


def rewrite_import_path(path):
    """
    Rewrite a sys.path-style list of import paths to resolve all symlinks
    on absolute directories.
    """
    for i, dirname in enumerate(path):
        if os.path.isabs(dirname):
            path[i] = os.path.realpath(dirname)


def load_tests(loader, standard_tests, pattern):
    # top level directory cached on loader instance
    this_dir = os.path.dirname(__file__)
    top_level_dir = os.path.dirname(os.path.dirname(this_dir))
    pattern = pattern or "test_*.py"
    # Workaround for http://bugs.python.org/issue19347
    rewrite_import_path(sys.path)
    rewrite_import_path(obelus.test.__path__)
    package_tests = loader.discover(start_dir=this_dir, pattern=pattern,
                                    top_level_dir=top_level_dir)
    standard_tests.addTests(package_tests)
    return standard_tests


if __name__ == '__main__':
    obelus.test.main()
