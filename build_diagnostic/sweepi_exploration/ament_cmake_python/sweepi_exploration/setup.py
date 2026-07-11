from setuptools import find_packages
from setuptools import setup

setup(
    name='sweepi_exploration',
    version='0.2.0',
    packages=find_packages(
        include=('sweepi_exploration', 'sweepi_exploration.*')),
)
