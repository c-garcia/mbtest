﻿# encoding=utf-8
import logging
import platform
import time
from collections.abc import Sequence
from pathlib import Path

import pexpect
import requests
from furl import furl
from more_itertools import flatten

DEFAULT_MB_EXECUTABLE = str(Path("node_modules") / ".bin" / ("mb.cmd" if platform.system() == "Windows" else "mb"))

logger = logging.getLogger(__name__)


class MountebankException(Exception):
    pass


class MountebankTimeoutError(MountebankException):
    pass


class MountebankServer(object):
    def __init__(self, executable=DEFAULT_MB_EXECUTABLE, port=2525, timeout=5):
        self.server_port = port
        try:
            self.mb_process = pexpect.spawn(executable, args=["--port", str(port), "--debug"])
            self._await_start(timeout)
            logger.info("Spawned mb process %s on port %s.", self.mb_process.pid, self.server_port)
        except OSError:
            logger.error("Failed to spawn mb process with executable at %s. Have you installed Mountebank?", executable)
            raise

    def __call__(self, imposters):
        self.imposters = imposters
        return self

    def __enter__(self):
        self.imposter_ports = self.create_imposters(self.imposters)
        return self

    def __exit__(self, ex_type, ex_value, ex_traceback):
        self.delete_imposters()

    def _await_start(self, timeout):
        self.mb_process.expect("now taking orders", timeout=timeout)
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                requests.get(self.server_url, timeout=1).raise_for_status()
                started = True
                break
            except Exception:
                started = False
                time.sleep(0.1)

        if not started:  # pragma: no cover
            raise MountebankTimeoutError("Mountebank failed to start within {0} seconds.".format(timeout))

        logger.debug("Server started at %s.", self.server_url)

    def create_imposters(self, definition):
        if isinstance(definition, Sequence):
            return list(flatten(self.create_imposters(imposter) for imposter in definition))
        else:
            json = definition.as_structure()
            post = requests.post(self.server_url, json=json, timeout=10)
            post.raise_for_status()
            definition.port = post.json()["port"]
            return [definition.port]

    def delete_imposters(self):
        for imposter_port in self.imposter_ports:
            requests.delete(self.imposter_url(imposter_port)).raise_for_status()

    def get_actual_requests(self):
        impostors = {}
        for imposter_port in self.imposter_ports:
            response = requests.get(self.imposter_url(imposter_port), timeout=5)
            response.raise_for_status()
            json = response.json()
            impostors[imposter_port] = json["requests"]
        return impostors

    @property
    def server_url(self):
        return furl().set(scheme="http", host="localhost", port=self.server_port, path="imposters")

    def imposter_url(self, imposter_port):
        return furl(self.server_url).add(path="{0}".format(imposter_port))

    def close(self):
        self.mb_process.close()
        self.mb_process.wait()
        logger.info(
            "Terminated mb process %s on port %s status %s.",
            self.mb_process.pid,
            self.server_port,
            self.mb_process.exitstatus,
        )


def mock_server(request, executable=DEFAULT_MB_EXECUTABLE, port=2525, **kwargs):
    """A mock server, running one or more impostors, one for each site being mocked.

    Use in a pytest conftest.py fixture as follows:

    @pytest.fixture(scope="session")
    def mock_server(request):
        return server.mock_server(request)

    Test will look like:

    def test_1_imposter(mock_server):
        imposter = Imposter(Stub(Predicate(path='/test'),
                                 Response(body='sausages')),
                            record_requests=True)

        with mock_server(imposter) as s:
            r = requests.get('{0}/test'.format(imposter.url))

            assert_that(r, is_(response_with(status_code=200, body="sausages")))
            assert_that(s, had_request(path='/test', method="GET"))

    This function can take optional keyword arguments:

    * timeout - specifies how long to wait for the Mountebank server to start.
    * port - Server port
    * executable - Alternate location for the Mountebank executable.
    """
    server = MountebankServer(executable=executable, port=port, **kwargs)

    def close():
        server.close()

    request.addfinalizer(close)

    return server
