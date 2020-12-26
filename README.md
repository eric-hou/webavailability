# Introduction 
This is a project to track and report Websites availabilities. It contains two components - Tracker and Recorder.
Tracker probes Websites and pushes the availability status messages to Kafka Cluster.
Recorder takes the messages from Kafka and records status messages in PostgresSQL server.

# Tracker
Tracker detects URLs through HTTP get and optionally, checks the page content against provided regexp.
It provides the following metrics along with two fixed information - location and URL.
* status - One of "responsive, "unresponsive"
* phrase - One of all HTTP status strings and four additional ones- 'domain not exist', 'ssl error', 'connection timeout', 'Page content not expected'
* dns - DNS resolve cost
* response - Page load cost
* detail - When page content doesn't match the provided regular expression, this filed holds the regular expression.

Tracker polls all provided URLs at the specified interval sending the status to the specified Kafka server in msgpack format (https://msgpack.org/index.html).

# Recorder
Recorder takes messages which it is interested in from the specified Kafka and stores it in the specified PostgreSQL server.
Only messages for interested domains are subscribed.
## ENUM types definition
As mentioned above, there are two types of strings are tracked - *status* and *phrase*.
To validate the input and save table space, two ENUM types are defined.

    CREATE TYPE response_status AS ENUM ('responsive', 'unresponsive');

    CREATE TYPE phrase_status AS ENUM ('continue', 'switching protocols', 'processing', 'ok', 'created', 'accepted', 'non-authoritative information', 'no content', 'reset content', 'partial content', 'multi-status', 'already reported', 'im used', 'multiple choices', 'moved permanently', 'found', 'see other', 'not modified', 'use proxy', 'temporary redirect', 'permanent redirect', 'bad request', 'unauthorized', 'payment required', 'forbidden', 'not found', 'method not allowed', 'not acceptable', 'proxy authentication required', 'request timeout', 'conflict', 'gone', 'length required', 'precondition failed', 'request entity too large', 'request-uri too long', 'unsupported media type', 'requested range not satisfiable', 'expectation failed', 'misdirected request', 'unprocessable entity', 'locked', 'failed dependency', 'upgrade required', 'precondition required', 'too many requests', 'request header fields too large', 'unavailable for legal reasons', 'internal server error', 'not implemented', 'bad gateway', 'service unavailable', 'gateway timeout', 'http version not supported', 'variant also negotiates', 'insufficient storage', 'loop detected', 'not extended', 'network authentication required', 'domain not exist', 'ssl error', 'connection timeout', 'Page content not expected');

## How tables are organized
Recorder stores messages in PostgreSQL tables by domains, which means the tables' number is decided by that of domains and all tables are identical.
The table name is in the format of 'web_activity_<domain>' with domain name's dots replaced by underscores.

### Table definition
As is mentioned above, all the tables are identical with different table names only.

For example, the following TABLE CREATE statement is for aiven.io

    CREATE TABLE IF NOT EXISTS web_activity_aiven_io ( id SERIAL PRIMARY KEY, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, topic_offset bigint DEFAULT -1, test_from varchar(32) NOT NULL, url varchar(256) NOT NULL, event_time BIGINT, status response_status, phrase phrase_status, dns integer DEFAULT -1, response integer DEFAULT -1, detail varchar(128) );

Fields description:
* id - SERIAL type, auto-incremented by PostgreSQL
* created_at - TIMESTAMP type, defaulted with PostgreSQL server's current timestamp
* topic_offset - BIGINT, which is the corresponding topic offset for this row
* test_from - varchar(32), where *Tracker* is run from. It is a fixed value set by *Tracker*.
* url - varchar(256), URL which is tested against
* event_time - BIGINT, the epoch seconds in UTC when status message is generated in Tracker
* status - response_status ENUM type
* phrase - phrase_status EnUM type
* dns - integer, cost of DNS resolving
* response - integer, cost of loading the page
* detail - varchar(128), regular expression string which fails to be verified.

### URL index
For a quick lookup based on URL, an index is built on *url* field on every table.
For example, the following statement is for creating an index for *url* on table *web_activity_aiven_io*.

    CREATE INDEX IF NOT EXISTS web_activity_url_index_aiven_io ON web_activity_aiven_io (url);

# Build and Test
## To build a pypi package
    pipenv install --dev
    pipenv shell
    python setup.py sdist bdist_wheel
## To run a unittest
    pipenv install --dev
    pipenv shell
    pytest
## To build a docker image
### For tracker
    docker build -t webavailability-tracker -f Dockerfile-tracker .
### For recorder
    docker build -t webavailability-recorder -f Dockerfile-recorder .

# Run
## Run from pipenv directly
### To run Tracker
An example command is provided as follows. Follow the help to change the parameters.

    pipenv install
    pipenv run python tracker.py -l sydney -w https://www.google.com,https://aiven.io -k "kafka-3f77ed08-benben3956-6e6a.aivencloud.com:20276" -c "C:\Users\EricHou\Downloads\aiven\ca.pem" -e "C:\Users\EricHou\Downloads\aiven\service.cert" -y "C:\Users\EricHou\Downloads\aiven\service.key" -p 30

### To run Recorder
An example command is provided as follows. Follow the help to change the parameters.

    pipenv install
    pipenv run python recorder.py -d www.google.com,aiven.io -k "kafka-3f77ed08-benben3956-6e6a.aivencloud.com:20276" -c "C:\Users\EricHou\Downloads\aiven\ca.pem" -e "C:\Users\EricHou\Downloads\aiven\service.cert" -y "C:\Users\EricHou\Downloads\aiven\service.key" -p "postgres://username:password@pg-9971643-benben3956-6e6a.aivencloud.com:20274/webavailability?sslmode=require" -g "C:\Users\EricHou\Downloads\aiven\pgca.pem"

## Run from docker image
### How to run Tracker
* Prepare your Kafka server CA file, your Kafka client access certificate file and access key file in a directory.
* Prepare a text file which contains all environment variables like the following. Details of environments meaning can
be found in tracker.py.

      LOCATION=SYDNEY
      # 'https://aiven.io <svg\s+' means the loaded page will be checked against regexp '<svg\s+'
      WEBSITES=https://www.google.com,https://aiven.io <svg\s+
      PERIOD=30
      KAFKA=kafka-3f77ed08-benben3956-6e6a.aivencloud.com:20276
      CA=/tmp/certs/ca.pem
      CERT=/tmp/certs/service.cert
      KEY=/tmp/certs/service.key
  
* Run it
  
Run it like the following.
  
      docker run -v C:\Users\EricHou\Downloads\aiven\:/tmp/certs --env-file C:\Users\EricHou\tests\tracker.txt -it webavailability-tracker

### How to run Recorder
* Prepare your PostgreSQL CA file, Kafka server CA file, your Kafka client access certificate file and access key file in a directory.
* Prepare a text file which contains all environment variables like the following. Details of environments meaning can
  be found in recorder.py. 
  
      DOMAIN=www.google.com,aiven.io 
      KAFKA=kafka-3f77ed08-benben3956-6e6a.aivencloud.com:20276
      CA=/tmp/certs/ca.pem
      CERT=/tmp/certs/service.cert
      KEY=/tmp/certs/service.key
      POSTGRES=postgres://username:password@pg-9971643-benben3956-6e6a.aivencloud.com:20274/webavailability?sslmode=require
      GPCA=/tmp/certs/pgca.pem
  
* Run it 
  
Run it like the following

      docker run -v C:\Users\EricHou\Downloads\aiven\:/tmp/certs --env-file C:\Users\EricHou\tests\recorder.txt -it webavailability-recorder
