from setuptools import setup

setup(
    name='near',
    version='0.2',
    py_modules=['near'],
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        near=near:cli
    ''',
)
