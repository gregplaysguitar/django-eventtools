#!/usr/bin/env python
# coding: utf8

from setuptools import setup, find_packages
from setuptools.command.test import test

# avoid importing the module 
exec(open('eventtools/_version.py').read())

setup(
    name='eventtools',
    version=__version__,
    description='Recurring event tools for django',
    long_description=open('readme.md').read(),
    author='Greg Brown',
    author_email='greg@gregbrown.co.nz',
    url='https://github.com/gregplaysguitar/django-eventtools',
    packages=find_packages(),
    zip_safe=False,
    platforms='any',
    install_requires=['Django>=1.8',],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Framework :: Django',
    ],
)
