from decimal import ROUND_HALF_UP, Decimal


def calculate_cost_rp(kwh: float, tariff_sen: int, extra_percent: float = 0.0) -> int:
    """Hitung biaya listrik dalam integer Rupiah menggunakan Decimal.

    Rumus: Decimal(str(kwh)) * Decimal(tariff_sen) * (100 + extra_percent) / 10000
    dibulatkan dengan ROUND_HALF_UP ke integer terdekat.
    """
    dec_kwh = Decimal(str(kwh))
    dec_tariff_sen = Decimal(tariff_sen)
    dec_extra = Decimal(str(extra_percent))
    numerator = dec_kwh * dec_tariff_sen * (Decimal("100") + dec_extra)
    cost = numerator / Decimal("10000")
    return int(cost.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_tariff_to_sen(tariff_str: str) -> int:
    """Konversi string input tarif (Rp desimal dengan koma atau titik) ke integer sen.

    Contoh: '1444.70' atau '1444,70' -> 144470.
    """
    clean_str = tariff_str.strip().replace(",", ".")
    dec_rp = Decimal(clean_str)
    dec_sen = dec_rp * Decimal("100")
    return int(dec_sen.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
