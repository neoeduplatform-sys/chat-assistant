import os
from unittest import mock

from app.env_utils import env_bool, env_int, env_raw


def test_env_raw_strips_inline_comment():
    with mock.patch.dict(os.environ, {"FOO": "true # not a comment for docker"}, clear=False):
        assert env_raw("FOO") == "true"


def test_env_bool_true():
    with mock.patch.dict(os.environ, {"FLAG": "yes"}, clear=False):
        assert env_bool("FLAG") is True


def test_env_int_strips_comment():
    with mock.patch.dict(os.environ, {"K": "40 # chunks"}, clear=False):
        assert env_int("K", 3) == 40
