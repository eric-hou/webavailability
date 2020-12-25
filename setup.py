from setuptools import setup, find_packages

setup(
    name='WebAvailability',
    use_scm_version={"write_to": "_version.py", "fallback_version": "1.0"},
    author='Liang Hou',
    author_email='eric.hou.liang@gmail.com',
    description='A simple tool for tracking Website Availability',
    url='https://ericlianghou.visualstudio.com/webavailability',
    setup_requires=['setuptools_scm'],
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "dnspython",
        "requests",
        "kafka-python",
        "postgres",
    ],
    python_requires='>=3.6',
)
