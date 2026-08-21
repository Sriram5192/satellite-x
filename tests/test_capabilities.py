from satellite_x.capabilities import capability_registry


def test_external_capabilities_never_claim_unsafe_completion():
    items = {item.code: item for item in capability_registry()}
    assert items["sentinel1_rtc"].status == "implemented_evidence_only"
    for code in ["government_land_records", "phone_otp", "yield_prediction", "vra_machinery", "mobile_offline"]:
        assert items[code].status == "implemented_activation_required"
    for item in items.values():
        assert item.activation_requirements
        assert item.unsafe_shortcut
