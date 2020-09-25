"""
****************************************************************************************************
URBANopt™, Copyright (c) 2019-2020, Alliance for Sustainable Energy, LLC, and other contributors.
All rights reserved.
Redistribution and use in source and binary forms, with or without modification, are permitted
provided that the following conditions are met:
Redistributions of source code must retain the above copyright notice, this list of conditions
and the following disclaimer.
Redistributions in binary form must reproduce the above copyright notice, this list of conditions
and the following disclaimer in the documentation and/or other materials provided with the
distribution.
Neither the name of the copyright holder nor the names of its contributors may be used to endorse
or promote products derived from this software without specific prior written permission.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
****************************************************************************************************
"""

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
