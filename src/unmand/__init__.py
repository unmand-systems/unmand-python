"""Upload a Swarm task"""
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

class Job:
    """Represents a job running on the Exfil API"""

    def __init__(self, job_id, status):
        self.job_id = job_id
        self.status = status
        self.time_queued = time.time()
        self.time_finished = None
        self.result = None

    def update_status(self, status):
        """Change status of the job"""
        self.status = status

    def save_result(self, result):
        """Save job result"""
        self.time_finished = time.time()
        self.result = result

    def __repr__(self):
        return '<{}: Id={} Status={}>'.format(self.__class__.__name__, self.job_id, self.status)


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

        if isinstance(self.status, str):
            if self.status not in ['FAILURE', 'SUCCESS']:
                raise Exception('Status must be one of "FAILURE" or "SUCCESS"')
        else:
            raise Exception('Status must be a string and one of "FAILURE" or "SUCCESS"')

        if isinstance(self.environment, str):
            if self.environment not in ['TEST', 'UAT', 'PROD']:
                raise Exception("""Status must be one of "TEST", "UAT", or "PROD" """)
            if self.environment == 'UAT':
                self.environment = 'TEST'
        else:
            raise Exception("""Status must be a string and one of "TEST", "UAT", or "PROD" """)

        if not isinstance(self.outcome, str):
            raise Exception('Response must be a string')
        if not self.outcome[0].isupper():
            raise Exception('First letter of response must be upper case')

        if not isinstance(self.data, (dict, list)) and self.data is not None:
            raise Exception('Details must be JSON compatible: list or dictionary')

    def __repr__(self):
        return '<{}: Id={} Status={}>'.format(self.__class__.__name__, self.guid, self.status)

class ExfilAPI:
    """Implements a connection to the Exfil API"""

    def __init__(self, token, test=False):
        self.token = token
        if test:
            self.url = 'https://exfil-uat.unmand.app/'
        else:
            self.url = 'https://exfil.unmand.app/'

    def queue(self, file_data, uuid=None):
        """Submit a document for prediction"""
        files = {
            "file": file_data
        }

        data = {
            "model": uuid
        }

        if uuid:
            r = requests.post(self.url + 'predictions/', files=files, data=data, auth=TokenAuth(self.token))
        else:
            r = requests.post(self.url + 'predictions/', files=files, auth=TokenAuth(self.token))

        if r.status_code == requests.codes.created: # pylint: disable=no-member
            response = r.json()
            return Job(response.get('jobId'), response.get('status'))
        return Job(None, 'FAILED')

    def poll(self, job, max_tries=100, interval=10.0, suppress_output=False): # pylint: disable=too-many-branches
        """Check if prediction is done"""

        # Helper function
        def estimate_job_time(bounding_box_count):
            return 0.000014 * (bounding_box_count ** 2) + (0.02255 * bounding_box_count) + 1.08

        try_count = 0

        params = {
            "jobId": job.job_id,
        }

        while job.status not in ['FAILED', 'FINISHED']:
            time.sleep(interval)

            r = requests.post(self.url + 'predictions/result', params, auth=TokenAuth(self.token))

            if r.status_code == requests.codes.ok: # pylint: disable=no-member
                response = r.json()

                job.update_status(response.get('status'))

                if job.status == 'QUEUED':
                    try_count += 1
                    if try_count > max_tries:
                        if not suppress_output:
                            logging.error('API not responding')
                        job.update_status('FAILED')
                        return job
                elif job.status == 'STARTED':
                    wait_period = estimate_job_time(response.get('numberOfBboxes'))
                    if not suppress_output:
                        logging.info('Job running: Estimated job length {:.1f}s'.format(wait_period))
                    time.sleep(wait_period)
                elif job.status == 'FAILED':
                    if not suppress_output:
                        logging.error('Job failed')
                    return job
                elif job.status == 'FINISHED':
                    result = {
                        'total_time': response.get('timeTaken'),
                        'feature_extraction_time': response.get('timeTakenFeatureExtraction'),
                        'time_in_queue': response.get('timeInQueue'),
                        'data': response.get('data'),
                        'bboxes': response.get('bboxes')
                    }
                    job.save_result(result)
                    if not suppress_output:
                        logging.info('Job completed')
                    return job
            else:
                job.update_status('FAILED')
                if not suppress_output:
                    logging.error('API not responding or responding with error state')
                return job

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
        params = {k: v for k, v in task.__dict__.items()} # pylint: disable=unnecessary-comprehension
        r = requests.post(self.url + 'tasks/create', json=params, auth=TokenAuth(self.token))
        if r.status_code == requests.codes.created:  # pylint: disable=no-member
            return r.json()
        logging.error(f'API returned {r.status_code}') # pylint: disable=logging-fstring-interpolation
        return False

    def update_swarm_task(self, task):
        """Update a Swarm task"""
        params = {k: v for k, v in task.__dict__.items()} # pylint: disable=unnecessary-comprehension
        r = requests.put(self.url + f'tasks/{task.id}', json=params, auth=TokenAuth(self.token))
        if r.status_code == requests.codes.ok:  # pylint: disable=no-member
            return r.json()
        logging.error(f'API returned {r.status_code}') # pylint: disable=logging-fstring-interpolation
        return False
