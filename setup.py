
from distutils.core import setup

import obelus

version = obelus.__version__

with open('README.rst') as f:
    long_description = f.read()

setup(
    name="obelus",
    version=version,
    packages = ["obelus", "obelus.agi", "obelus.ami", "obelus.test"],
    author="Optiflows",
    author_email="rand@optiflows.com",
    maintainer="Antoine Pitrou",
    maintainer_email="antoine@python.org",
    url="https://pypi.python.org/pypi/obelus/",
    download_url="https://bitbucket.org/optiflowsrd/obelus/get/tip.zip",
    license="MIT",
    description="Protocol implementation of the Asterisk Manager Interface "
                "and Asterisk Gateway Interface",
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Topic :: Communications :: Telephony',
        ],
    long_description=long_description,
    keywords=["asterisk", "manager", "gateway", "interface", "AMI", "AGI",
              "twisted", "tornado", "tulip"],
)
