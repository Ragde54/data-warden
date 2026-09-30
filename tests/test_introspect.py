import pytest
from sqlalchemy import create_engine, text

from data_warden import synthetic
from data_warden.introspect import collect_samples, sample_column, text_columns


@pytest.fixture
def engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'demo.db'}"
    synthetic.write_database(url, synthetic.generate(rows=50))
    return create_engine(url)


def test_finds_hidden_email_column(engine):
    assert ("customers", "col7") in text_columns(engine)


def test_ignores_non_text_columns(engine):
    found = set(text_columns(engine))
    assert ("orders", "amount") not in found
    assert ("customers", "id") not in found
    assert ("employees", "hired_year") not in found


def test_sample_respects_limit(engine):
    assert len(sample_column(engine, "customers", "col7", limit=5)) == 5


def test_sample_skips_nulls_and_blanks(engine):
    with engine.begin() as conn:
        conn.execute(text("update customers set col7 = NULL where id <= 10"))
        conn.execute(text("update customers set col7 = '' where id between 11 and 20"))
    values = sample_column(engine, "customers", "col7", limit=1000)
    assert len(values) == 30
    assert all(v for v in values)


def test_collect_samples_covers_every_text_column(engine):
    samples = list(collect_samples(engine, limit=10))
    assert {(s.table, s.column) for s in samples} == set(text_columns(engine))
    assert all(len(s.values) <= 10 for s in samples)


def test_hostile_identifier_is_not_executed_as_sql(engine):
    with pytest.raises(Exception):  # noqa: B017 - any DB error is fine, injection is not
        sample_column(engine, "customers; drop table customers; --", "col7")
    assert ("customers", "col7") in text_columns(engine)
