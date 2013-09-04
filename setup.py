
from distutils.core import setup
import sys

version = "0.1.dev"

with open('README.rst') as f:
    long_description = f.read()

setup(
    name="obelus",
    version=version,
    packages = ["obelus", "obelus.agi", "obelus.ami", "obelus.test"],
    author="Antoine Pitrou",
    author_email="antoine@python.org",
    url="",
    license="",
    description="Protocol implementation of the Asterisk Manager Interface "
                "and Asterisk Gateway Interface",
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        ],
    long_description=long_description,
)
