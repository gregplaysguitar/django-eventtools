#!/usr/bin/env python
# coding: utf8

import os

from setuptools import setup, find_packages

# if there's a converted readme, use it, otherwise fall back to markdown
if os.path.exists('README.rst'):
    readme_path = 'README.rst'
else:
    readme_path = 'README.md'

# avoid importing the module
exec(open('eventtools/_version.py').read())

setup(
    name='django-eventtools',
    version=__version__,
    description='Recurring event tools for django',
    long_description=open(readme_path).read(),
    author='Greg Brown',
    author_email='greg@gregbrown.co.nz',
    url='https://github.com/gregplaysguitar/django-eventtools',
    packages=find_packages(),
    license='BSD License',
    zip_safe=False,
    platforms='any',
    install_requires=['Django>=1.8', 'python-dateutil>=2.1'],
    include_package_data=True,
    package_data={},
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Framework :: Django',
    ],
)
