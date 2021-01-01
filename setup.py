from setuptools import setup, find_packages

setup(
    name='WebsitesAvailability',
    version="v1.1.0",
    author='Liang Hou',
    author_email='eric.hou.liang@gmail.com',
    license='Apache 2.0',
    description='A production-ready Website Availability tracking system',
    url='https://github.com/eric-hou/webavailability',
    setup_requires=['setuptools_scm'],
    packages=find_packages(exclude='tests'),
    scripts=['tracker.py', 'recorder.py'],
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "msgpack",
        "dnspython",
        "requests",
        "pyOpenSSL",
        "kafka-python",
        "psycopg2",
    ],
    python_requires='>=3.6',
)
