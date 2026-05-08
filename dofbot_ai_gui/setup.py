from setuptools import find_packages, setup

package_name = 'dofbot_ai_gui'

import os

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'scripts'), ['dofbot_ai_gui/app.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='roboholic_harsh',
    maintainer_email='harshpjadav165@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'main = dofbot_ai_gui.main:main',
        ],
    },
)
