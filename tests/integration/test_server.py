# encoding=utf-8
import logging
from pathlib import Path

import pytest
import requests
from brunns.matchers.response import response_with
from hamcrest import assert_that, is_
from pexpect import ExceptionPexpect

from mbtest.imposters import Imposter, Predicate, Response, Stub
from mbtest.matchers import had_request
from mbtest.server import MountebankServer, MountebankException

logger = logging.getLogger(__name__)


def test_request_to_mock_server(mock_server):
    # Start mock server with required behavior
    imposter = Imposter(Stub(Predicate(path="/test"), Response(body="sausages")))

    with mock_server(imposter) as server:
        # Make request to mock server
        response = requests.get("{0}/test".format(imposter.url))

        assert_that("We got the expected response", response, is_(response_with(status_code=200, body="sausages")))
        assert_that("The mock server recorded the request", server, had_request(path="/test", method="GET"))


def test_nonexistent_executable():
    with pytest.raises(ExceptionPexpect):
        MountebankServer(executable=str(Path(".") / "no" / "such" / "path"))


def test_non_executable():
    with pytest.raises(ExceptionPexpect):
        MountebankServer(executable=str(Path(".") / "README.md"))


def test_executable_not_mb():
    with pytest.raises(MountebankException):
        MountebankServer(executable="ls", port=2526, timeout=1)


@pytest.mark.xfail
def test_exception_running_multiple_servers_on_same_port():
    # Given
    with pytest.raises(MountebankException):
        try:
            server1 = MountebankServer(port=2526)
            server2 = MountebankServer(port=2526)
        finally:
            server1.close()
            server2.close()


def test_allow_multiple_servers_on_different_ports():
    # Given
    try:
        server1 = MountebankServer(port=2526)
        server2 = MountebankServer(port=2527)
        imposter1 = Imposter(Stub(Predicate(path="/test"), Response(body="sausages")))
        imposter2 = Imposter(Stub(Predicate(path="/test"), Response(body="bacon")))

        with server1(imposter1), server2(imposter2):

            response1 = requests.get("{0}/test".format(imposter1.url))
            response2 = requests.get("{0}/test".format(imposter2.url))

            assert_that(response1, is_(response_with(status_code=200, body="sausages")))
            assert_that(response2, is_(response_with(status_code=200, body="bacon")))

    finally:
        server1.close()
        server2.close()
