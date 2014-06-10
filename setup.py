"""Setup file for distribution"""
from setuptools import setup

with open("README.rst") as fh:
    long_description = fh.read()

with open("VERSION") as fh:
    version = fh.read().strip()

setup(
    name = "ftrace_frag",
    version = version,
    license = "GPLv3",
    description = "Program to parse FTRACE output and obtain execution fragments",
    long_description = long_description,
    py_modules=["timestamp"],
    package_dir = {"":"src"},
    classifiers = ["Development Status :: 3 - Alpha",
                   "License :: OSI Approved :: GPLv3",
                   "Programming Language :: Python",
                  "Programming Language :: Python :: 2.7"],
    entry_points = {"console_scripts": ["ftrace_frag = ftrace_frag:main"]}
    )
