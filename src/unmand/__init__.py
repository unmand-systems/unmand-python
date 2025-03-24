"""Upload a Swarm task"""
import os
import time
import logging
from datetime import datetime

import requests
from requests.auth import AuthBase


class TokenAuth(AuthBase): # pylint: disable=too-few-public-methods
    """Implements a custom authentication scheme."""

    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        """Attach an API token to a custom auth header."""
        r.headers['Authorization'] = self.token
        return r


class Extraction:
    """Represents an extraction running on Exfil API"""

    def __init__(self, extraction_guid, status):
        self.guid = extraction_guid
        self.status = status
        self.time_queued = time.time()
        self.time_finished = None
        self.result = None

    def update_status(self, status):
        """Change status of the extraction"""
        self.status = status

    def save_result(self, result):
        """Save extraction result"""
        self.time_finished = time.time()
        self.result = result

    def __repr__(self):
        return f'<{self.__class__.__name__}: Id={self.guid} Status={self.status}>'


class Task: # pylint: disable=too-few-public-methods, too-many-instance-attributes
    """Represents a Swarm task outcome"""

    def __init__(self, task_id, start, finish, status, environment, response, details, custom_column1, custom_column2, custom_column3): # pylint: disable=too-many-arguments, too-many-branches, unused-argument
        self.guid: str = task_id #pylint: disable=invalid-name
        self.created: str = start
        self.updated: str = finish
        self.status: str = status
        self.environment: str = environment
        self.stages: list = []
        self.outcome: str = response
        self.data: str = details
        self.swarm_version: str = 'N/A'

        # Run validation
        if not isinstance(self.guid, str):
            raise Exception('Id must be a string')

        if self.created is not None and not isinstance(self.created, datetime):
            raise Exception('Start value must be a datetime object if provided')
        if self.created is not None:
            self.created = self.created.isoformat()
        if self.updated is not None and not isinstance(self.updated, datetime):
            raise Exception('End value must be a datetime object if provided')
        if self.updated is not None:
            self.updated = self.updated.isoformat()

        if not isinstance(self.status, str):
            raise Exception('Status must be a string and one of "FAILURE" or "SUCCESS"')

        if self.status not in ['FAILURE', 'SUCCESS']:
            raise Exception('Status must be one of "FAILURE" or "SUCCESS"')
        if not isinstance(self.environment, str):
            raise Exception("""Status must be a string and one of "TEST", "UAT", or "PROD" """)

        if self.environment not in ['TEST', 'UAT', 'PROD']:
            raise Exception("""Status must be one of "TEST", "UAT", or "PROD" """)
        if self.environment == 'UAT':
            self.environment = 'TEST'
        if not isinstance(self.outcome, str):
            raise Exception('Response must be a string')
        if not self.outcome[0].isupper():
            raise Exception('First letter of response must be upper case')

        if not isinstance(self.data, (dict, list)) and self.data is not None:
            raise Exception('Details must be JSON compatible: list or dictionary')

    def __repr__(self):
        return f'<{self.__class__.__name__}: Id={self.guid} Status={self.status}>'


class ExfilAPI:
    """Implements a connection to the Exfil API"""

    def __init__(self, token, test=False):
        self.token = token
        if test:
            self.url = os.getenv('EXFIL_API_URL', 'https://exfil-uat.unmand.app/')
        else:
            self.url = os.getenv('EXFIL_API_URL', 'https://exfil.unmand.app/')

    def queue(self, file_data, guid=None):
        """Submit a document for prediction"""
        files = {"file": file_data}
        payload = {
            'source': 'API',
        }

        if guid:
            logging.info('Using specified model version')
            payload['model'] = guid

        result = requests.post(
            f'{self.url}projects/extractions',
            files=files,
            auth=TokenAuth(self.token),
            data=payload
        )

        if result.status_code == requests.codes.created:  # pylint: disable=no-member
            response = result.json()
            return Extraction(response.get('extractionGuid'), response.get('status'))

        return Extraction(None, 'FAILED')

    def poll(self, extraction, max_tries=100, interval=10.0, suppress_output=False, with_probabilities=False, with_positions=False):  # pylint: disable=too-many-branches
        """Check if prediction is done"""

        # Helper function
        def estimate_extraction_time(bounding_box_count):
            """Estimate extraction time based on number of bounding boxes"""
            return 0.000014 * (bounding_box_count ** 2) + (0.02255 * bounding_box_count) + 1.08

        try_count = 0

        extraction_guid = extraction.guid

        while extraction.status not in ['FAILED', 'FINISHED']:
            time.sleep(interval)

            result = requests.get(
                f'{self.url}extractions/{extraction_guid}/data', auth=TokenAuth(self.token),
                params={'probabilities': with_probabilities, 'positions': with_positions}
            )

            if result.status_code == requests.codes.ok:  # pylint: disable=no-member
                response = result.json()

                extraction.update_status(response.get('status'))

                if extraction.status == 'QUEUED':
                    try_count += 1
                    if try_count > max_tries:
                        if not suppress_output:
                            logging.error('API not responding')
                        extraction.update_status('FAILED')
                        return extraction

                elif extraction.status == 'STARTED':
                    wait_period = estimate_extraction_time(
                        len(response.get('bboxes', [])))
                    if not suppress_output:
                        logging.info('Extraction running: Estimated extraction length {:.1f}s'.format(wait_period))
                    time.sleep(wait_period)

                elif extraction.status == 'FAILED':
                    if not suppress_output:
                        logging.error('Extraction failed')
                    return extraction

                elif extraction.status == 'FINISHED':
                    result = {
                        'total_time': response.get('timeTaken'),
                        'feature_extraction_time': response.get('timeTakenFeatureExtraction'),
                        'time_in_queue': response.get('timeInQueue'),
                        'data': response.get('data'),
                        'bboxes': response.get('bboxes')
                    }

                    extraction.save_result(result)

                    if not suppress_output:
                        logging.info('Extraction completed')

                    return extraction

            else:
                extraction.update_status('FAILED')
                if not suppress_output:
                    logging.error('API not responding or responding with error state')
                return extraction


class SwarmAPI:
    """Implements a connection to the Exfil API"""

    def __init__(self, token, test=False):
        self.token = token
        if test:
            self.url = 'https://swarm-uat.unmand.app/'
        else:
            self.url = 'https://swarm.unmand.app/'

    def upload_swarm_task(self, task):
        """Upload a Swarm task"""
        params = dict(task.__dict__.items())
        r = requests.post(
            f'{self.url}tasks/create', json=params, auth=TokenAuth(self.token)
        )
        if r.status_code == requests.codes.created:  # pylint: disable=no-member
            return r.json()
        logging.error(f'API returned {r.status_code}') # pylint: disable=logging-fstring-interpolation
        return False

    def update_swarm_task(self, task):
        """Update a Swarm task"""
        params = dict(task.__dict__.items())
        r = requests.put(
            f'{self.url}tasks/{task.id}', json=params, auth=TokenAuth(self.token)
        )
        if r.status_code == requests.codes.ok:  # pylint: disable=no-member
            return r.json()
        logging.error(f'API returned {r.status_code}') # pylint: disable=logging-fstring-interpolation
        return False
