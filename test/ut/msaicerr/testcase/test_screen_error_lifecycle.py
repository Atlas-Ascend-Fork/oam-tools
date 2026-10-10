#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------

"""Exercise restoration through real decorated functions and exceptions."""

import pytest
from ms_interface import utils


@pytest.fixture(autouse=True)
def preserve_error_cache():
    root = utils.ExceptionRootCause()
    previous = root.cache_error
    try:
        yield root
    finally:
        root.cache_error = previous


@pytest.mark.parametrize("initial", [True, False])
def test_exception_restores_previous_state(preserve_error_cache, initial):
    root = preserve_error_cache
    root.cache_error = initial
    error = ValueError("expected test failure")

    @utils.screen_error
    def fail():
        assert root.cache_error is False
        raise error

    with pytest.raises(ValueError) as caught:
        fail()
    assert caught.value is error
    assert root.cache_error is initial


@pytest.mark.parametrize("initial", [True, False])
def test_success_preserves_return_and_state(preserve_error_cache, initial):
    root = preserve_error_cache
    root.cache_error = initial
    marker = object()

    @utils.screen_error
    def succeed(value):
        assert root.cache_error is False
        return value

    assert succeed(marker) is marker
    assert succeed.__name__ == "succeed"
    assert root.cache_error is initial


def test_nested_exception_preserves_outer_screen(preserve_error_cache):
    root = preserve_error_cache
    root.cache_error = True

    @utils.screen_error
    def inner():
        raise ValueError("nested failure")

    @utils.screen_error
    def outer():
        with pytest.raises(ValueError):
            inner()
        assert root.cache_error is False

    outer()
    assert root.cache_error is True


def test_real_path_validation_error_restores_cache(preserve_error_cache):
    root = preserve_error_cache
    root.cache_error = True
    with pytest.raises(utils.AicErrException):
        utils.check_path_valid("")
    assert root.cache_error is True
