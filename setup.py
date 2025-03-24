"""Core module for making requests to Unmand APIs"""
import setuptools


def readme():
    """Pull README file for long documentation string"""
    with open("README.md", "r") as f:
        return f.read()

setuptools.setup(name='unmand',
    version='2.1.2',
    description='Helper library for consuming the Unmand API',
    url='https://github.com/unmand-systems/unmand-python',
    author='Josiah Khor',
    author_email='josiah.khor@unmand.com',
    long_description=readme(),
    long_description_content_type="text/markdown",
    project_urls={
        "Bug Tracker": "https://github.com/unmand-systems/unmand-python/issues",
    },
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    install_requires=['requests'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent"
        ],
    python_requires=">=3.11",
    zip_safe=False)
