"""Tests for the persona catalog."""

from banksym.capabilities.txgen.personas import PERSONAS, profile_for


def test_known_personas_present():
    for pid in ["gig_worker", "affluent_family", "student", "retiree", "young_professional"]:
        assert pid in PERSONAS


def test_profile_for_known():
    profile = profile_for("affluent_family")
    assert profile.id == "affluent_family"
    assert profile.monthly_income > 0


def test_profile_for_unknown_returns_default():
    profile = profile_for("does_not_exist")
    assert profile.id == "default"


def test_profile_for_none_returns_default():
    assert profile_for(None).id == "default"
