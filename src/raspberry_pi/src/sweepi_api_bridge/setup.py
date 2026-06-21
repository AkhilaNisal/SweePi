from glob import glob
from os.path import join

from setuptools import find_packages, setup

package_name = 'sweepi_api_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', [join('resource', package_name)]),
        (join('share', package_name), ['package.xml']),
        (join('share', package_name, 'launch'), glob(join('launch', '*.launch.py'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='akhila-wedamestrige',
    maintainer_email='wedamestrigean@gmail.com',
    description='LAN API bridge and runtime storage for SweePi.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'api_bridge_node = sweepi_api_bridge.api_bridge_node:main',
        ],
    },
)
