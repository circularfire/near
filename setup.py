from setuptools import setup

setup(
    name="near",
    version='0.1',
    py_modules=['near'],
    install_requires=[
        'Click',
    ],
    entry_points = {
        'console_scripts': ['near=near:go'],
    }
)
