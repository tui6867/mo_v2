from dataclasses import replace

import pytest

from outreach.domain.recipients import (
    Recipient,
    combine,
    csv_preview,
    email_key,
    finalize,
    generate,
    import_csv,
    normalize_email,
    parse_manual,
    resolve,
)


def test_explicit_email_csv_and_headers():
    data = b"First,Last,Email\nSynthetic,Person,person@EXAMPLE.com\n"
    rows = import_csv(data, {"first_name": "First", "last_name": "Last", "email": "Email"}, 1000)
    chosen = resolve(rows[0], "first.last", "elsewhere.example.com")
    assert chosen.chosen_email == "person@example.com"
    assert chosen.generated_email == ""
    assert chosen.source_row == 2
    assert csv_preview(data, 1000)[0] == ["First", "Last", "Email"]


def test_unicode_compound_names_and_email_only():
    data = "name,email\n李 小龍,synthetic@example.com\nAna María de la Cruz,compound@example.com\n,emailonly@example.com\n,\n".encode()
    rows = import_csv(data, {"full_name": "name", "email": "email"}, 1000)
    assert len(rows) == 3
    assert (rows[0].first_name, rows[0].last_name) == ("李", "小龍")
    assert rows[1].last_name == "María de la Cruz"
    assert not rows[2].first_name


@pytest.mark.parametrize(
    "data", [b"a,b\nx,y,z", b"a,b\nx", b"a,a\nx,y", b"\xff", b"", b'a,b\n"bad,y']
)
def test_malformed_csv(data):
    with pytest.raises(ValueError):
        csv_preview(data, 1000)


def test_upload_limit_mapping_append_replace():
    with pytest.raises(ValueError):
        csv_preview(b"name\nSynthetic", 2)
    with pytest.raises(ValueError):
        import_csv(b"name\nSynthetic", {"email": "missing"}, 100)
    a, b = Recipient(first_name="A"), Recipient(first_name="B")
    assert combine([a], [b], "append") == [a, b]
    assert combine([a], [b], "replace") == [b]
    with pytest.raises(ValueError):
        combine([a], [b], "")


def test_manual_structured_records():
    rows = parse_manual(
        "Synthetic Compound Name <synthetic@example.com>\nonly@example.com\n李 小龍\n\n"
    )
    assert rows[0].last_name == "Compound Name"
    assert rows[0].explicit_email == "synthetic@example.com"
    assert rows[1].first_name == ""
    assert rows[2].first_name == "李"
    assert rows[2].source_row == 3


def test_manual_multiple_or_malformed_addresses_not_silently_truncated():
    for line in (
        "one@example.com, two@example.com",
        "Name <bad>",
        "Name <one@example.com> trailing",
    ):
        row = parse_manual(line)[0]
        assert row.explicit_email
        assert not resolve(row, "first", "example.com").chosen_email


@pytest.mark.parametrize(
    "pattern,expected",
    [("first.last", "élise.王"), ("flast", "é王"), ("firstl", "élise王"), ("first", "élise")],
)
def test_generated_unicode_not_transliterated(pattern, expected):
    assert generate("Élise", "王", pattern, "example.com") == expected + "@example.com"
    assert (
        "guess"
        in resolve(Recipient(first_name="Élise", last_name="王"), pattern, "example.com").validation
    )


@pytest.mark.parametrize(
    "first,last,pattern",
    [
        ("Ana María", "Cruz", "flast"),
        ("Ana", "de la Cruz", "flast"),
        ("A", "", "flast"),
        ("A", "B", "f.last"),
        ("", "B", "first"),
    ],
)
def test_generation_limitations(first, last, pattern):
    with pytest.raises(ValueError):
        generate(first, last, pattern, "example.com")


def test_normalization_final_edit_dedup_and_invalid_explicit():
    assert normalize_email(" Person@EXAMPLE.com ") == "Person@example.com"
    a = Recipient(chosen_email="Person@EXAMPLE.com")
    assert len(finalize([a, replace(a, chosen_email="person@example.com")])) == 1
    bad = resolve(
        Recipient(first_name="A", last_name="B", explicit_email="invalid"), "flast", "example.com"
    )
    assert not bad.chosen_email  # Never silently replace invalid explicit data with guesses.
    with pytest.raises(ValueError):
        finalize([Recipient(chosen_email="bad")])
    assert email_key("groß@example.com") != email_key("gross@example.com")
