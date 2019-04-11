from os.path import join
from setuptools import setup, find_packages

with open('README.md') as f:
    long_description = f.read()

def get_version():
    with open(join('deus_state_machina', '__init__.py')) as f:
        for line in f:
            if line.startswith('__version__ ='):
                return line.split('=')[1].strip().strip('"\'')

setup(
    name='deus_state_machina',
    version=get_version(),
    description='A django state machine, saving you from race-condition sadness',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Tom Wallroth',
    author_email='tomwallroth@gmail.com',
    url='https://github.com/TierMobility/deus-state-machina/',
    license='MIT',
    packages=find_packages(),
    install_requires=[],
    classifiers=[
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'License :: OSI Approved :: MIT License',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
    ],
    zip_safe=False,
)
