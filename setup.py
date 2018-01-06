from setuptools import setup, find_packages

setup(
    name="theseus.dht",
    version="0.0.1",
    description="Flexible and secure distributed hash table",
    long_description="For details, see https://wootfish.github.io/theseus.dht",
    url="https://github.com/wootfish/theseus.dht",
    author="Eli Sohl",
    license="GPLv3",
    packages=find_packages(exclude=["test", "docs", "venv"]),
    install_requires=["noiseprotocol", "twisted"],
    python_requires=">=3.5",
)
