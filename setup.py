# Thingswise Digital Machine: An Advanced Streaming Analytics Framework for IoT
#    Copyright (C) 2017 Thingswise, LLC
#


import os
from os import path
import sys
import subprocess
from setuptools import setup


# with open('requirements.txt') as f:
#     required = f.read().splitlines()

setup(
    name = "tw-network-manager",
    version = "0.0.1",
    author = "Thingswise",
    author_email = "info@thingswise.com",
    description = ("Thingswise Network Manager"),

    # keywords = "example documentation tutorial",
    # url = "http://packages.python.org/an_example_pypi_project",
    packages=['twnm'],
    # long_description=read('README'),

    # install_requires=required
)