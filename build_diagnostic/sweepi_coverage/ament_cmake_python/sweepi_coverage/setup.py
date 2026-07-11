from setuptools import find_packages
from setuptools import setup

setup(
    name='sweepi_coverage',
    version='0.1.0',
    packages=find_packages(
        include=('sweepi_coverage', 'sweepi_coverage.*')),
)
