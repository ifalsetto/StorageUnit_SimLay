from app.services.valuation import percentile, remove_iqr_outliers


def test_percentile():
    assert percentile([10, 20, 30, 40], 50) == 25
    assert percentile([10, 20, 30], 50) == 20


def test_iqr_keeps_small_samples():
    assert remove_iqr_outliers([10, 20, 1000]) == [10, 20, 1000]
