"""Property content: encode and decode, and the errors of each."""

import math

import pytest

from rangekeeper.model.content import decode, encode
from rangekeeper.schema.records import PropertyContent
from rangekeeper.shared.errors import DecodeError, EncodingError


def test_content_that_cannot_be_encoded_raises_encoding_error():
    cycle: list[object] = []
    cycle.append(cycle)
    for value in (math.inf, cycle):
        with pytest.raises(EncodingError):
            encode(value)
    with pytest.raises(TypeError, match="unsupported property type"):
        encode(object())


def test_content_that_does_not_decode_raises_decode_error():
    for data in (
        {"kind": "integer", "text": "01"},
        {"kind": "integer", "text": "one"},
        {"kind": "boolean", "text": "yes"},
        {"kind": "set", "items": [{"kind": "null"}, {"kind": "null"}]},
    ):
        with pytest.raises(DecodeError):
            decode(PropertyContent.from_data(data))
    assert decode(encode({"a": (1, 2.5)})) == {"a": (1, 2.5)}
