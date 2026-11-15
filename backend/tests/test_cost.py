from app.services.cost import calculate_cost_rp, parse_tariff_to_sen


def test_calculate_cost_exact_decimal() -> None:
    # Uji kasus wajib: 3.2 kWh, tarif 144470 sen, extra 0 -> Rp4.623
    cost = calculate_cost_rp(kwh=3.2, tariff_sen=144470, extra_percent=0.0)
    assert cost == 4623


def test_calculate_cost_with_extra_percent() -> None:
    # 10 kWh, tarif Rp1.500/kWh (150000 sen), extra 10% (PPJ) -> 10 * 1500 * 1.10 = 16.500
    cost = calculate_cost_rp(kwh=10.0, tariff_sen=150000, extra_percent=10.0)
    assert cost == 16500


def test_parse_tariff_to_sen() -> None:
    assert parse_tariff_to_sen("1444.70") == 144470
    assert parse_tariff_to_sen("1444,70") == 144470
    assert parse_tariff_to_sen("1500") == 150000
    assert parse_tariff_to_sen("  1352.00  ") == 135200

