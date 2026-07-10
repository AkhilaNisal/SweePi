from glob import glob
from setuptools import setup


package_name = 'sweepi_temp_rpi_hardware'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='akhila-wedamestrige',
    maintainer_email='wedamestrigean@gmail.com',
    description='Raspberry Pi GPIO hardware layer for SweePi test drive and cleaning motors.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'stepper_driver_node = sweepi_temp_rpi_hardware.stepper_driver_node:main',
            'stepper_ticks_to_odom_node = sweepi_temp_rpi_hardware.stepper_ticks_to_odom_node:main',
            'mpu6050_imu_node = sweepi_temp_rpi_hardware.mpu6050_imu_node:main',
            'cleaning_motor_controller_node = sweepi_temp_rpi_hardware.cleaning_motor_controller_node:main',
        ],
    },
)
