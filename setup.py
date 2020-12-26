from setuptools import setup, find_packages

setup(
    name='WebsitesAvailability',
    version="v1.0.1",
    author='Liang Hou',
    author_email='eric.hou.liang@gmail.com',
    description='A production-ready Website Availability tracking system',
    url='https://github.com/eric-hou/webavailability',
    setup_requires=['setuptools_scm'],
    packages=find_packages(exclude='tests'),
    scripts=['tracker.py', 'recorder.py'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
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
