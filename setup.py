from setuptools import setup, find_packages
from setuptools.command.develop import develop
import os

command = 'git clone -b timeseries_updates https://github.com/NREL/ditto.git'
os.system(command)

setup(
    version="0.1.0",
    author="Tarek Elgindy",
    author_email="tarek.elgindy@nrel.gov",
    packages=find_packages(),
    python_requires='>=3.7',
    install_requires=[
        'opendssdirect.py'
    ]
)
