from setuptools import find_packages
from setuptools import setup

setup(
    name='sweepi_robot_manager_interfaces',
    version='0.1.0',
    packages=find_packages(
        include=('sweepi_robot_manager_interfaces', 'sweepi_robot_manager_interfaces.*')),
)
