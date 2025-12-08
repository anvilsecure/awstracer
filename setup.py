import setuptools
import re

name = "awstracer"

# We could use import obviously but we parse it as some python build systems
# otherwise pollute namespaces and we might end up with some annoying issues.
# See https://stackoverflow.com/a/7071358 for a discussion.
vfile = "src/{}/_version.py".format(name)
with open(vfile, "rt") as fd:
    verstrline = fd.read()
    regex = r"^__version__ = ['\"]([^'\"]*)['\"]"
    mo = re.search(regex, verstrline, re.M)
    if mo:
        version = mo.group(1)
    else:
        raise RuntimeError("Unable to find version string in %s." % (vfile,))

# load long description directly from the include markdown README
with open("README.md", "r") as fd:
    long_description = fd.read()

setuptools.setup(
    name=name,
    version=version,
    author="Anvil Secure",
    author_email="info@anvilsecure.com",
    description="AWS cli trace recorder and player",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/anvilsecure/awstracer",
    packages=setuptools.find_packages(where="src"),
    package_dir={"": "src"},
    keywords="AWS awscli cli tracer recorder player utility",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Operating System :: POSIX",
        "Operating System :: MacOS :: MacOS X",
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.6",
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
    ],
    python_requires='>=3.6',
    entry_points={
        "console_scripts": ["awstrace-play=awstracer.player:main",
                            "awstrace-rec=awstracer.recorder:main"]
    },
    install_requires=[
        "awscli>=1.18.39",
        "botocore>=1.15.39"
    ],
    extras_require={
        "test": ["tox", "flake8"]
    }
)
