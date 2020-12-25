# Introduction 
This is a project to track and report Websites availabilites. It contains two components. One probes Websites and pushes
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

# Contribute
TODO: Explain how other users and developers can contribute to make your code better. 

If you want to learn more about creating good readme files then refer the following [guidelines](https://docs.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops). You can also seek inspiration from the below readme files:
- [ASP.NET Core](https://github.com/aspnet/Home)
- [Visual Studio Code](https://github.com/Microsoft/vscode)
- [Chakra Core](https://github.com/Microsoft/ChakraCore)