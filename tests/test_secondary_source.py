from io import BytesIO

import pandas as pd

import shm.checks.data_quality as data_quality


def test_spy_check_uses_latest_three_complete_common_years() -> None:
    dates = pd.to_datetime(
        [
            "2022-01-03",
            "2022-12-30",
            "2023-01-03",
            "2023-12-29",
            "2024-01-02",
            "2024-12-31",
            "2025-01-02",
            "2025-11-20",
        ]
    )
    primary = pd.DataFrame(
        {"date": dates, "close": [100, 110, 100, 120, 100, 130, 100, 999]}
    )
    secondary = pd.DataFrame(
        {"date": dates, "close": [100, 110.5, 100, 120.5, 100, 130.5, 100, 1]}
    )

    result = data_quality.check_spy_annual_returns(primary, secondary)

    assert result.status == "PASS"
    assert "2022=" in result.detail
    assert "2024=" in result.detail
    assert "2025=" not in result.detail


def test_stooq_spy_mirror_normalizes_columns_and_dates(monkeypatch) -> None:
    payload = (
        b"Data,Otwarcie,Najwyzszy,Najnizszy,Zamkniecie,Wolumen\n"
        b"2024-01-02,10,11,9,10.5,100\n"
        b"2024-01-03,11,12,10,11.5,200\n"
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self) -> bytes:
            return payload

    monkeypatch.setattr(data_quality, "urlopen", lambda *_args, **_kwargs: Response())

    frame = data_quality.download_stooq_spy("2024-01-03", "2024-01-03")

    assert frame.to_dict("records") == [
        {"date": pd.Timestamp("2024-01-03"), "close": 11.5}
    ]
