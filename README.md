# Introduction 
This is a project to track and report Websites availabilities. It contains two components. One probes Websites and pushes
the availability status messages to Kafka Cluster. The other one takes the messages from Kafka and records status
messages in PostgresSQL server.

# Getting Started
1.	Installation process
      pip install webavailability
2.	Software dependencies are installed automatically.
3.	Latest releases
4.	API references

# Build and Test
## To build
    pipenv install --dev
    pipenv shell
    python setup.py sdist bdist_wheel
## To test
    pipenv install --dev
    pipenv shell
    pytest

# Run
