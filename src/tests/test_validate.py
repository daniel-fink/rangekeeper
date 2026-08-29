import rangekeeper as rk


def test_is_text_accepts_strings_and_optionally_rejects_empty_text():
    assert rk.validate.is_text("Apartment 27.05")
    assert rk.validate.is_text("")
    assert rk.validate.is_text("   ")
    assert not rk.validate.is_text("", empty=False)
    assert not rk.validate.is_text("   ", empty=False)


def test_is_text_rejects_non_strings_without_restricting_characters():
    assert not rk.validate.is_text(None)
    assert not rk.validate.is_text(27)
    assert rk.validate.is_text("area.nsa.internal", empty=False)
    assert rk.validate.is_text("A302:L302", empty=False)
