"""
****************************************************************************************************
URBANopt™, Copyright (c) 2019-2022, Alliance for Sustainable Energy, LLC, and other
contributors. All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this list
of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or other
materials provided with the distribution.

Neither the name of the copyright holder nor the names of its contributors may be
used to endorse or promote products derived from this software without specific
prior written permission.

Redistribution of this software, without modification, must refer to the software
by the same designation. Redistribution of a modified version of this software
(i) may not refer to the modified version by the same designation, or by any
confusingly similar designation, and (ii) must refer to the underlying software
originally provided by Alliance as “URBANopt”. Except to comply with the foregoing,
the term “URBANopt”, or any confusingly similar designation may not be used to
refer to any modified version of this software or any modified version of the
underlying software originally provided by Alliance without the prior written
consent of Alliance.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
OF THE POSSIBILITY OF SUCH DAMAGE.
****************************************************************************************************
"""

from setuptools import setup, find_packages

requirements = ["ditto.py~=0.2.3", "opendssdirect.py~=0.6.1"]

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="urbanopt-ditto-reader",
    version="0.5.0",
    author="Tarek Elgindy",
    author_email="tarek.elgindy@nrel.gov",
    description="Enhancement of URBANopt GeoJSON that can be consumed by DiTTo reader",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/urbanopt/urbanopt-ditto-reader",
    license="Custom",
    packages=find_packages(exclude=("tests", "docs", "example")),
    python_requires='>=3.7',
    py_modules=['ditto_reader_cli'],
    include_package_data=True,
    install_requires=requirements,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.10"
    ],
    entry_points='''
        [console_scripts]
        ditto_reader_cli=urbanopt_ditto_reader.ditto_reader_cli:cli
        update_licenses=update_licenses:update_licenses
    '''
)
