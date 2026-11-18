"""Endpoint tests: the five routes, the row schema, and malformed input.

No endpoint had ever been tested. The suite checked the functions behind them, which
leaves out everything the HTTP layer adds: query-param coercion, the JSON encoding of
a missing value, what happens to a request nobody anticipated, and what a client sees
when the dataset is not there.

Three defects came out of writing this file, all of them "wrong answer returned as an
answer" rather than crashes:

  * `top_n=-1` returned 200 with n-1 colleges, because DataFrame.head(-1) drops the
    last row instead of erroring. `top_n=0` returned the entire dataset.
  * `max_netprice=60000` -- one missing underscore -- was accepted, ignored, and
    answered with the default-filtered list.
  * A missing dataset surfaced as a 500 from inside numpy.

Input validation also appears in Phase 5. It is done here because these are the tests
that found it, and a bound with no test is a bound nobody maintains.
"""
import json
import os

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import ROW_FIELDS, app

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SYNTHETIC = os.path.join(FIXTURES, "ipeds_synthetic")

# The five endpoints this app serves. There were seven; /api/rag/* was removed in
# Phase 3.5 because its only data source was generated, not IPEDS.
ENDPOINTS = ["/api/health", "/api/meta", "/api/colleges",
             "/api/education/distributions", "/api/merit-policy"]

# Every way a caller can get /api/colleges wrong, and the status it must produce.
# The requirement is a 4xx that names the problem -- never a 200 with a plausible
# ranking, and never a 500.
BAD_REQUESTS = [
    ("top_n=-1", 422),                   # silently returned n-1 rows
    ("top_n=0", 422),                    # silently returned the whole dataset
    ("top_n=abc", 422),
    ("top_n=99999", 422),                # above the 2000 cap
    ("max_net_price=abc", 422),
    ("max_net_price=-5", 422),           # a negative price is not a filter
    ("mgi_at_least_median=maybe", 422),
    ("exclude_flagged=sometimes", 422),
    ("nonsense=1", 400),                 # unknown parameter
    ("max_netprice=60000", 400),         # the realistic typo
]


@pytest.fixture
def client(data_dir):
    """TestClient over the synthetic fixture dataset."""
    data_dir(SYNTHETIC)
    return TestClient(app)


def _strict_json(response):
    """Parse the body the way a browser does -- NaN and Infinity are not JSON.

    Python's json.loads accepts them by default, so a response full of bare NaN
    tokens would pass a naive test and fail in every browser. parse_constant fires on
    exactly those tokens.
    """
    def reject(token):
        raise AssertionError(f"{token} is not valid JSON")

    return json.loads(response.text, parse_constant=reject)


@pytest.mark.parametrize("url", ENDPOINTS)
def test_every_endpoint_answers_with_valid_json(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.text
    assert _strict_json(r) is not None


@pytest.mark.parametrize("url", ["/api/rag/status", "/api/rag/query"])
def test_the_removed_rag_endpoints_stay_removed(client, url):
    """Phase 3.5 deleted them: the mission text they answered from was generated,
    not IPEDS, and IPEDS has published no mission file since 2007."""
    assert client.get(url).status_code == 404


def test_the_row_schema_is_exactly_the_contract(client):
    """observed-api-contract.md pins 27 fields. The frontend reads them by name, so
    a field that quietly disappears breaks a column with no error anywhere."""
    body = client.get("/api/colleges?top_n=5&mgi_at_least_median=false").json()
    assert body["count"] == len(body["colleges"]) > 0

    for row in body["colleges"]:
        assert list(row.keys()) == ROW_FIELDS
    assert len(ROW_FIELDS) == 27


def test_a_missing_value_is_null_not_nan(client):
    """999003's SAT and admit rate are -2 sentinels in the file. They must arrive as
    JSON null -- a bare NaN is invalid JSON and would take the whole table down."""
    body = _strict_json(client.get("/api/colleges?top_n=50&mgi_at_least_median=false"))
    rows = {r["UNITID"]: r for r in body["colleges"]}

    assert rows[999003]["SATVR75"] is None
    assert rows[999003]["SAT_TOTAL_75"] is None
    assert rows[999003]["ADMISSIONS_RATE"] is None
    assert rows[999003]["DATA_GAPS"] == "no_sat,no_admit_rate"
    # And a row that has the value still carries it.
    assert rows[999001]["SAT_TOTAL_75"] == 1220


@pytest.mark.parametrize("query,expected", BAD_REQUESTS)
def test_malformed_parameters_get_a_4xx_that_names_the_problem(client, query, expected):
    r = client.get(f"/api/colleges?{query}")
    assert r.status_code == expected, f"{query} -> {r.status_code} {r.text[:200]}"

    # The name of the offending parameter has to be in the body, or the client is
    # left guessing which of five filters it got wrong.
    param = query.split("=")[0]
    assert param in r.text


def test_top_n_minus_one_no_longer_returns_a_plausible_ranking(client):
    """The defect this bound exists for. `head(-1)` drops the last row, so the
    request came back 200 with one fewer college and nothing to indicate that the
    list was not the answer to the question asked."""
    ok = client.get("/api/colleges?top_n=3&mgi_at_least_median=false")
    assert ok.status_code == 200 and ok.json()["count"] == 3

    bad = client.get("/api/colleges?top_n=-1&mgi_at_least_median=false")
    assert bad.status_code == 422
    assert "colleges" not in bad.json()


def test_unknown_filters_are_rejected_rather_than_ignored(client):
    """A typo in a filter name used to be answered with the default-filtered list --
    a different question, answered confidently."""
    r = client.get("/api/colleges?max_netprice=60000")
    assert r.status_code == 400

    detail = r.json()["detail"]
    assert "max_netprice" in detail
    # And it says what is accepted, so the fix does not need the source.
    for name in ["max_net_price", "top_n", "exclude_flagged"]:
        assert name in detail


def test_an_empty_result_is_an_empty_list_not_an_error(client):
    """No college costs under $0. That is a legitimate answer, not a failure."""
    r = client.get("/api/colleges?max_net_price=0")
    assert r.status_code == 200
    assert r.json() == {"count": 0, "colleges": []}


def test_the_filters_filter_what_they_claim_to(client):
    """Each filter, through HTTP, on a dataset whose expected membership is known."""
    def ids(query):
        body = client.get(f"/api/colleges?{query}").json()
        return [r["UNITID"] for r in body["colleges"]]

    base = "top_n=50&mgi_at_least_median=false"

    # 999009's average grant exceeds its entire cost of attendance, so it is flagged.
    # Default view drops it; turning the filter off brings it back rather than
    # hiding it permanently.
    assert 999009 not in ids(base)
    assert 999009 in ids(f"{base}&exclude_flagged=false")

    # Unscoreable rows are never ranked, with the flag filter off or on: 999004 has
    # no graduation rate and 999010 no recoverable sticker.
    assert 999004 not in ids(f"{base}&exclude_flagged=false")
    assert 999010 not in ids(f"{base}&exclude_flagged=false")

    # Price filter.
    assert ids(f"{base}&max_net_price=15000") == [999002]

    # top_n truncates the ranking, and RANK stays 1..n with no gaps.
    body = client.get(f"{'/api/colleges?' + base}&top_n=2").json()
    assert [r["RANK"] for r in body["colleges"]] == [1, 2]


def test_meta_publishes_the_defaults_the_frontend_starts_from(client):
    """The sidebar initialises from these. If they drift from config, the first view
    a user sees is not the view the API says is the default."""
    m = client.get("/api/meta").json()
    assert m["defaults"] == config.DEFAULTS
    assert [d["key"] for d in m["dimensions"]] == [
        "sticker", "grant", "net_price", "admit_rate", "grad_rate", "sat"]


def test_distributions_ship_the_shape_of_the_dataset(client):
    """The sandbox re-scores a hypothetical college in the browser, so the server
    ships percentile breakpoints once instead of a request per slider pixel."""
    d = _strict_json(client.get("/api/education/distributions"))

    assert d["n"] == 8                 # the whole fixture dataset
    assert d["scored_n"] == 6          # 999004 and 999010 have no Value Score
    assert len(d["value_score_breakpoints"]) == 101

    # The three Value Score inputs, each with p0..p100 and the direction it improves
    # in. `higher_is_better` has to travel with the data: net price is the component
    # where a bigger number is a worse college.
    assert set(d["components"]) == {"net_price", "grad_rate", "aid_share"}
    for key, comp in d["components"].items():
        assert len(comp["breakpoints"]) == 101, key
        assert comp["breakpoints"] == sorted(comp["breakpoints"]), key
    assert d["components"]["net_price"]["higher_is_better"] is False
    assert d["components"]["grad_rate"]["higher_is_better"] is True

    s = d["dimensions"]["sticker"]
    assert s["n"] == 7                 # 999010's sticker is unrecoverable
    assert len(s["bin_edges"]) == len(s["bin_counts"]) + 1
    assert sum(s["bin_counts"]) == s["n"]


def test_merit_policy_reports_coverage_not_completeness(client):
    """The endpoint's job is to say how far the sourcing got. `verified` read against
    the dataset size would imply the rest came back negative."""
    body = client.get("/api/merit-policy").json()
    cov = body["coverage"]

    assert cov["verified"] == len(body["verified"])
    assert cov["unresolved"] == len(body["unresolved"])
    assert cov["attempted"] == cov["verified"] + cov["unresolved"]
    assert "top 50" in cov["scope"]
    assert "attempted" in body["note"]

    # Every record carries its own provenance: no verdict without a source.
    for rec in body["verified"]:
        assert rec["source_url"].startswith("http")
        assert rec["cds_year"] and rec["line_n"]


def test_a_missing_dataset_is_a_503_naming_the_file_not_a_500(data_dir, tmp_path):
    """The deploy failure mode made diagnosable. `deploy/k8s/backend.yaml` mounts an
    emptyDir, so a restarted pod serves exactly this state; `curl /api/meta` now
    names the missing file and the directory it looked in."""
    data_dir(tmp_path)
    c = TestClient(app, raise_server_exceptions=False)

    r = c.get("/api/meta")
    assert r.status_code == 503
    assert "HD2022.csv" in r.json()["detail"]

    # Health stays up: the process is fine, the data is not.
    assert c.get("/api/health").status_code == 200
