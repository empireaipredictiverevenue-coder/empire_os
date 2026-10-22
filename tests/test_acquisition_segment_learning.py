from empire_os.acquisition_segment_learning import segment_pool

def item(ref, niche, product):
    return {"prospect_ref": ref, "niche": niche, "product_code": product,
            "company": "Example", "offer": "Reviewed proposal", "trigger": "Expansion",
            "trigger_ref": "source:1", "offer_ref": "offer:1",
            "company_identity_verified": True, "dated_commercial_trigger_verified": True,
            "product_fit_verified": True, "trigger_independently_verified": True,
            "offer_approved": True}

def test_niche_product_isolated():
    x=segment_pool(lane="vc_portfolio", records=[
        item("a", "Dental", "Growth Brief"), item("b", "Dental", "Growth Brief"),
        item("c", "Roofing", "Quote Matching")])
    assert len(x["segments"]) == 2
    assert x["segments"][0]["discovered"] == 2
    assert not x["model_training_authorized"]

def test_missing_segment_remains_unclassified():
    x=segment_pool(lane="contractor_quote", records=[item("a", "", "")])
    assert x["segments"][0]["niche"] == "unclassified"
    assert x["segments"][0]["product_code"] == "unclassified"
    assert x["segments"][0]["verified_conversion_rate"] is None

def test_no_fabricated_learning():
    x=segment_pool(lane="vc_portfolio", records=[item("a", "Legal", "Data")])
    assert x["segments"][0]["learning_eligible"] is False
    assert x["segments"][0]["settled_revenue"] is None
