"""Budowa warstwy Silver z pliku Bronze z notowaniami.

Wejście:  bronze_notowania.csv (separator ";", UTF-8 z BOM). Plik nie jest modyfikowany.
Wyjście:  silver_notowania.csv - poprawne, znormalizowane, unikalne po (date, ticker)
          odrzuty.csv          - błędne rekordy w oryginalnej postaci
          duplikaty.csv        - starsze poprawne wersje w oryginalnej postaci

Uruchomienie:  python silver.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

KATALOG = Path(__file__).resolve().parent
PLIK_BRONZE = KATALOG / "bronze_notowania.csv"
PLIK_SILVER = KATALOG / "silver_notowania.csv"
PLIK_ODRZUTY = KATALOG / "odrzuty.csv"
PLIK_DUPLIKATY = KATALOG / "duplikaty.csv"

SEP = ";"
KODOWANIE = "utf-8-sig"  # UTF-8 z BOM, przy odczycie BOM jest usuwany z nazwy pierwszej kolumny
KLUCZ = ["date_norm", "ticker_norm"]  # klucz biznesowy po normalizacji


def wczytaj_bronze(sciezka: Path) -> pd.DataFrame:
    """Wczytuje Bronze bez żadnej interpretacji: każda wartość jest tekstem,
    a puste pole zostaje pustym napisem (nie NaN). Dzięki temu odrzuty
    i duplikaty można zapisać dokładnie w postaci źródłowej."""
    return pd.read_csv(
        sciezka,
        sep=SEP,
        encoding=KODOWANIE,
        dtype=str,
        keep_default_na=False,
    )


def dodaj_kolumny_pomocnicze(bronze: pd.DataFrame) -> pd.DataFrame:
    """Normalizacja i parsowanie w kolumnach pomocniczych - oryginalne kolumny zostają nietknięte."""
    df = bronze.copy()

    # Reguła 1: ticker bez spacji na brzegach, wielkimi literami.
    df["ticker_norm"] = df["ticker"].str.strip().str.upper()

    # Data musi być prawdziwą datą w formacie RRRR-MM-DD; inaczej NaT.
    df["date_parsed"] = pd.to_datetime(df["date"].str.strip(), format="%Y-%m-%d", errors="coerce")
    df["date_norm"] = df["date_parsed"].dt.strftime("%Y-%m-%d")

    # Liczby: pusty napis i tekst ("abc", "duzo") zamieniają się w NaN.
    df["close_num"] = pd.to_numeric(df["close"].str.strip(), errors="coerce").astype(float)
    df["volume_num"] = pd.to_numeric(df["volume"].str.strip(), errors="coerce").astype(float)
    return df


def main() -> None:
    bronze = wczytaj_bronze(PLIK_BRONZE)
    df = dodaj_kolumny_pomocnicze(bronze)
    print(df.to_string())


if __name__ == "__main__":
    main()
