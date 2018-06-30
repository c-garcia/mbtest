from hamcrest import equal_to, anything, contains_string
from hamcrest.core.base_matcher import BaseMatcher
from hamcrest.core.core.isanything import IsAnything
from hamcrest.core.matcher import Matcher


def response_with(status_code=anything(), body=anything()):
    return ResponseMatcher(status_code=status_code, body=body)


class ResponseMatcher(BaseMatcher):
    def __init__(self, status_code=anything(), body=anything()):
        super(ResponseMatcher, self).__init__()
        self.status_code = status_code if isinstance(status_code, Matcher) else equal_to(status_code)
        self.body = body if isinstance(body, Matcher) else equal_to(body)

    def _matches(self, response):
        return self.status_code.matches(response.status_code) and self.body.matches(response.text)

    def describe_to(self, description):
        description.append_text("call with")
        self._optional_description(description)

    def _optional_description(self, description):
        self._append_matcher_descrption(description, self.status_code, "status_code")
        self._append_matcher_descrption(description, self.body, "body")

    def _append_matcher_descrption(self, description, matcher, text):
        if not isinstance(matcher, IsAnything):
            description.append_text(" {}: ".format(text)).append_description_of(matcher)

    def describe_mismatch(self, response, mismatch_description):
        mismatch_description.append_text("was response with status code: ").append_value(
            response.status_code
        ).append_text(" body: ").append_value(response.text)


def has_status_code(status_code):
    return response_with(status_code=status_code)


def has_body_containing(substring):
    return response_with(body=contains_string(substring))