from setuptools import setup

setup(
    name="theseus.dht",
    version="0.0.1",
    description="Flexible and secure distributed hash table",
    long_description="For details, see https://wootfish.github.io/theseus.dht",
    url="https://github.com/wootfish/theseus.dht",
    author="Eli Sohl",
    license="GPLv3",
    packages=['theseus', 'theseus.test'],
    install_requires=["noiseprotocol", "twisted", "PyNaCl"],
    python_requires=">=3.5",
)
