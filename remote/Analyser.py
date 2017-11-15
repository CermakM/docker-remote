"""Docker Remote Analyser - Handle remote docker repository"""

# Request libs
import json

import urllib3

from .Repository import DockerRepository, Tag

DOCKER_BASE_URL = 'https://hub.docker.com/v2/'
DOCKER_LOGIN_URL = 'https://hub.docker.com/v2/users/login/'


class DockerAnalyser:

    def __init__(self, repository, namespace="", url="", token=None):
        """Initialize Docker analyser to handle http requests"""
        # Disable warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.namespace = namespace
        self.repository_name = repository
        self.url = url
        self.token = token
        self.login = ""

        # Initialize controls
        self.http = urllib3.PoolManager()
        # Used for tracking current status and logging
        self.response = None

        # Get repository
        self.repository = self._get_repository()  # Repository object

    def set_credentials(self, username: str, password: str):
        self.login = {'username': username, 'password': password}

    def request_token(self) -> str:
        """Performs login to the docker hub and requests user token
        Sets up authorization header on success
        Uses cookies
        :returns: Authorization token, str
        :raises: urllib3.exceptions.HTTPError, KeyError
        """
        self.response = self.http.request('POST', DOCKER_LOGIN_URL, fields=self.login)
        self._check_response()
        try:
            self.http.headers['cookie'] = self.response.getheader('set-cookie')
            self.token = json.loads(self.response.data)['token']
        except KeyError as e:
            # TODO LOG
            raise e

        # Create authorization header
        self.http.headers['Authorization'] = "Bearer %s" % self.token

        return self.token

    @staticmethod
    def repo_to_url(repository, namespace="", site='repositories'):

        if namespace:
            namespace += '/'
        return "{base}{site}/{namespace}{repo}/".format(base=DOCKER_BASE_URL,
                                                        site=site,
                                                        namespace=namespace,
                                                        repo=repository)

    def _get_repository(self) -> DockerRepository:
        """
        :return: DockerRepository
        :raises: urllib3.exceptions.HTTPError
        """
        if not any((self.repository_name, self.url)):
            raise ValueError("Cannot get repository: "
                             "URL or repository name must be provided")

        if not self.url:
            self.url = self.repo_to_url(self.repository_name, self.namespace)
        # Get repository info
        self.response = self.http.request('GET', self.url)
        self._check_response()

        repository = DockerRepository(url=self.url)
        repository.add_info(data=json.loads(self.response.data, encoding='UTF-8'))

        # Get repository tags
        self.response = self.http.request('GET', self.url + 'tags/')
        self._check_response()

        repository.add_tags(data=json.loads(self.response.data, encoding='UTF-8'))

        return repository

    def get_tag(self, tag_name: str) -> Tag:

        return self.repository.tags[tag_name]

    def get_tags(self) -> list:

        return list(self.repository.tags.values())

    def get_tag_names(self) -> list:

        return list(self.repository.tags.keys())

    def get_description(self) -> tuple:

        return self.repository['description'], self.repository['full_description']

    def get_permissions(self) -> dict:
        return self.repository['permissions']

    def remove_tag(self, tag: str):
        """
        :param tag: tag id (name), str
        :raises: urllib3.exceptions.HTTPError
        """
        self.response = self.http.request('DELETE', self.url + 'tags/%s' % tag)
        self._check_response()

        self.repository.pop(tag, None)

    def _check_response(self, status=300):
        """Check status code and raises exception based on status argument
        :param status: status code that is tolerated
        :raises: urllib3.exceptions.HTTPError
        """
        if self.response.status >= status:
            self._raise_from_response()

    def _raise_from_response(self):
        """
        :raises: urllib3.exceptions.HTTPError
        """
        msg = "Error %d occurred: " % self.response.status
        msg += "%s, " % self.response.reason
        msg += self.response.data.decode('utf-8')
        # TODO LOG
        raise urllib3.exceptions.HTTPError(msg)

    def _check_tag(self, tag_name: str):
        """
        :param tag_name:
        :raises:  KeyError
        """
        if tag_name not in self.repository.tags:
            # TODO LOG, add did you mean?
            namespace = self.namespace + '/' if self.namespace else ""
            msg = "Tag {namespace}{repo}:{tag} does not exist".format(
                tag=tag_name,
                namespace=namespace,
                repo=self.repository_name
            )
            raise KeyError(msg)
