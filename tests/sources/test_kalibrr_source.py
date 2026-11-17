from jobradar.sources.job_source import SourceQuery
from jobradar.sources.kalibrr_source import KalibrrSource
from tests.conftest import FakeHttp


def test_parses_full_posting_with_pay_and_work_type(fixture_json):
    http = FakeHttp(fixture_json("kalibrr_search.json"))
    jobs = {job.ext_id: job for job in KalibrrSource(http).fetch(SourceQuery(terms=["vue"]))}

    remote = jobs["229598"]
    assert remote.work_type == "remote" and remote.remote is True
    assert (remote.salary_min, remote.salary_max, remote.currency, remote.salary_period) == (25000, 35000, "PHP", "month")
    assert remote.location == "Quezon City, NCR, Philippines"
    assert remote.url == "https://www.kalibrr.com/c/thinkbit/jobs/229598/vuejs-developer-work-from-home"
    assert "clean" in remote.description and "<" not in remote.description
    assert "vue" in remote.tags  # the site's own match counts as that skill

    onsite = jobs["1001"]
    assert onsite.work_type == "onsite"
    assert onsite.salary_min is None and onsite.salary_max is None  # pay hidden by the employer
    assert http.calls[0][1]["country"] == "Philippines"


def test_skips_work_types_you_do_not_accept(fixture_json):
    http = FakeHttp(fixture_json("kalibrr_search.json"))
    jobs = KalibrrSource(http).fetch(SourceQuery(terms=["vue"], work_types=["remote"]))
    assert [job.ext_id for job in jobs] == ["229598"]
