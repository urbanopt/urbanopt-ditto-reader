from setuptools import setup, find_packages
from setuptools.command.develop import develop
import os

# command = 'git clone -b timeseries_updates https://github.com/NREL/ditto.git'
command = 'git clone https://github.com/NREL/ditto.git'
os.system(command)

with open("LICENSE.md") as f:
    license = f.read()

setup(
    name="UrbanoptDittoReader",
    version="0.2.0",
    author="Tarek Elgindy",
    author_email="tarek.elgindy@nrel.gov",
    url="https://github.com/urbanopt/urbanopt-ditto-reader",
    license=license,
    packages=find_packages(exclude=("tests", "docs")),
    python_requires='>=3.7',
    install_requires=[
        'opendssdirect.py',
        'pandas',
        'networkx',
        'traitlets'
    ]
)
