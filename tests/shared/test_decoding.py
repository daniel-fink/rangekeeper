"""One JSON policy, one YAML policy and one JSON Pointer helper for every reader."""

import pytest

from rangekeeper.schema.records import Metadata
from rangekeeper.shared import pointer
from rangekeeper.shared.encoding import parse_json
from rangekeeper.shared.errors import ContractError, DecodeError
from rangekeeper.shared.validation import require_new
from rangekeeper.shared.yaml import decode


def test_pointer_escapes_each_token():
    assert pointer.escape("a/b~c") == "a~1b~0c"
    assert pointer.child("/items", 0, "x/y") == "/items/0/x~1y"
    assert pointer.child("") == ""


@pytest.mark.parametrize(
    "text, message",
    [
        ('{"a": 1, "a": 2}', "duplicate JSON key"),
        ('{"a": {"b": [], "b": []}}', "duplicate JSON key"),
        ('{"a": NaN}', "non-JSON number"),
        ("{", "Expecting"),
    ],
)
def test_parse_json_rejects_ambiguous_text(text, message):
    with pytest.raises(DecodeError, match=message):
        parse_json(text)


def test_record_and_codec_share_the_json_policy():
    with pytest.raises(DecodeError, match="duplicate JSON key"):
        Metadata.from_json('{"id": "x", "id": "y"}')


@pytest.mark.parametrize(
    "text, message",
    [
        ("a: 1\na: 2\n", "duplicate YAML key"),
        ("1: a\n", "keys must be strings"),
        ("a: !!python/name:os.system\n", "unsupported YAML tag"),
        ("base: &b {x: 1}\nother:\n  <<: *b\n", "merge keys"),
        ("a: [\n", "invalid YAML"),
    ],
)
def test_yaml_policy_rejects_unsafe_content(text, message):
    with pytest.raises(DecodeError, match=message):
        decode(text)


def test_yaml_policy_keeps_timestamps_as_strings():
    assert decode("date: 2026-01-31\n") == {"date": "2026-01-31"}


def test_require_new_is_the_duplicate_identity_check():
    identities: set = set()
    require_new(identities, "a")
    with pytest.raises(
        ContractError, match="duplicate Constraint identity: a"
    ) as error:
        require_new(identities, "a", label="Constraint identity", path="/c/0/id")
    assert error.value.code == "semantic.identity"
    assert error.value.path == "/c/0/id"
