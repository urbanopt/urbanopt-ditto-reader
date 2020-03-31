from setuptools import setup, find_packages
from setuptools.command.develop import develop

setup(
    version="0.1.0",
    author="Tarek Elgindy",
    author_email="tarek.elgindy@nrel.gov",
    packages=find_packages()
    python_requires '>=3.7'
    install_requiers=[
        'opendssdirect.py'
    ]
)
