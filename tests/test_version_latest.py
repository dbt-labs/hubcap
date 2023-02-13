from hubcap.version import latest_version


def test_latest_version():
    # Final versions take precedence over all pre-release versions
    assert latest_version(["1.2.1", "1.2.2", "1.2.3-rc"]) == "1.2.2"

    # A larger set of pre-release fields has a higher precedence than a smaller set
    # if all of the preceding identifiers are equal
    assert (
        latest_version(["1.2.2-rc3", "1.2.3-rc", "1.2.3-rc2", "1.2.3-a"]) == "1.2.3-rc2"
    )
