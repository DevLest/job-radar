from jobradar.sources.feed_collector import search_terms
from jobradar.sources.himalayas_source import HimalayasSource


def test_search_terms_fall_back_to_main_skills():
    assert search_terms({"sources": {"search_terms": ["laravel"]}, "skills": {"primary": ["vue"]}}) == ["laravel"]
    assert search_terms({"sources": {"search_terms": []}, "skills": {"primary": ["vue"]}}) == ["vue"]
    assert search_terms({}) == []


def test_himalayas_shortens_long_country_lists():
    assert HimalayasSource._location([]) == "Worldwide"
    assert HimalayasSource._location(["Philippines"]) == "Philippines"
    assert HimalayasSource._location(["Albania", "Brazil", "Philippines", "Peru"]) == "Philippines + 3 other countries"
