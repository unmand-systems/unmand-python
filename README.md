# Unmand Python Library

[![Version](https://img.shields.io/pypi/v/unmand.svg)](https://www.npmjs.org/package/unmand)

The Unmand Python library provides convenient access to the Unmand APIs from applications written in the Python language.

For more help, see our [docs](https://unmand.com/docs).

## Requirements

Python 3+
## Installation

Install the package with:

```sh
pip install unmand
```
## Example Usage

```python
from unmand import Extraction, ExfilAPI

token = 'TOP-SECRET-EXAMPLE-TOKEN'
document_path = 'Sample.pdf'

exfil = ExfilAPI(token)
with open(document_path, 'rb') as file_data:
    extraction = exfil.queue(file_data)
    print(extraction)
    if extraction.status != "FAILED":
        exfil.poll(extraction=extraction)
        if extraction.status == 'FINISHED':
            print(extraction.result)
```

## ExfilAPI and Extraction

The main class is ExfilAPI. Instantiate this with your token argument. Use the optional argument `test` to direct your queries to the test API instead of the production API. For example:

```python
exfil_test = ExfilAPI(token, test=True) # This aims at the test API
exfil = ExfilAPI(token) # This aims at the production API
```

Submit a extraction by attaching the binary file data from your system to the queue method of ExfilAPI. This will return an instance of the Extraction class.

```python
extraction = exfil.queue(file_data)
```

At any time, you can get the status of the extraction:

```python
print(extraction) # or
print(extraction.status)
```

Once a extraction is queued, call the poll method of the ExfilAPI class to be updated when the extraction is finished. Use the optional argument `suppress_output` to stop updates printing to screen.

```python
exfil.poll(extraction=extraction)  # or
exfil.poll(extraction=extraction, suppress_output=True)
```

Once finished, the results of the extraction are saved as a dictionary under the `result` attribute.

```python
print(extraction.result)
```


## Swarm Tasks

There is a SwarmAPI class so that swarm tasks can be uploaded for display in the UI. An example usage is shown below. Be careful, the token for a Swarm project will be different.

```python
swarm = SwarmAPI(token, test=True)

start_time = datetime.utcnow()
finish_time = datetime.utcnow()
response_details = {'Some data': 1, 'Some other data': 2, "an array": [1,2,3,4]}
status = 'SUCCESS' # or 'FAILURE'

task = Task('UniqueTestId', start_time, finish_time , status, 'PROD', 'Short Response', response_details , "First Identifier", "Second Identifier", "Third Identifier")
swarm.upload_swarm_task(task)
```