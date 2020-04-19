import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="awstracer",
    version="1.0",
    author="Anvil Ventures",
    author_email="info@anvilventures.com",
    description="TODO",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/anvilventures/awstracer",
    packages=setuptools.find_packages(where="src"),
    package_dir={"": "src"},
    keywords="AWS awscli recorder player tracer",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.6",
    ],
    python_requires='>=3.6',
    entry_points={
        "console_scripts": ["awstrace-play=awstracer.player:main",
                            "awstrace-rec=awstracer.recorder:main"]
    },
    install_requires=[
        "awscli",
        "botocore"
    ],
    extras_require={
        "test": ["tox", "flake8"]
    }
)
