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


def waliduj(df: pd.DataFrame) -> pd.DataFrame:
    """Zwraca tabelę błędów: jeden wiersz na rekord, jedna kolumna na regułę (True = reguła złamana)."""
    close = df["close_num"]
    volume = df["volume_num"]
    return pd.DataFrame(
        {
            # Reguła 2
            "brak_lub_zla_data": df["date_parsed"].isna(),
            "pusty_ticker": df["ticker_norm"] == "",
            # Reguła 3: skończona liczba > 0 (NaN i inf odpadają na np.isfinite)
            "zla_cena_close": ~(np.isfinite(close) & (close > 0)),
            # Reguła 4: skończona liczba całkowita >= 0; 0 jest poprawne, brak wartości nie
            "zly_wolumen": ~(np.isfinite(volume) & (volume >= 0) & (volume % 1 == 0)),
        },
        index=df.index,
    )


def sprawdz(warunek: bool, opis: str, bledy: list) -> None:
    print(f"  [{'OK' if warunek else 'BŁĄD'}] {opis}")
    if not warunek:
        bledy.append(opis)


def main() -> int:
    bronze = wczytaj_bronze(PLIK_BRONZE)
    kolumny_zrodlowe = list(bronze.columns)
    df = dodaj_kolumny_pomocnicze(bronze)

    # --- Krok 1 (reguła 5): najpierw wyodrębnij błędne rekordy -------------------------
    bledy_regul = waliduj(df)
    poprawny = ~bledy_regul.any(axis=1)
    powod = bledy_regul.apply(lambda wiersz: ", ".join(wiersz.index[wiersz]), axis=1)

    odrzuty = bronze.loc[~poprawny, kolumny_zrodlowe]  # oryginalne wiersze (reguła 7)
    poprawne = df.loc[poprawny]

    # --- Krok 2 (reguła 6): deduplikacja WYŁĄCZNIE wśród poprawnych ---------------------
    # Najnowsza wersja pierwsza; czasy są w jednym formacie ISO UTC, więc sortowanie tekstowe
    # jest poprawne. Ponieważ błędne rekordy już odpadły, nowszy błędny rekord nie może
    # wyprzeć starszego poprawnego (reguła 7).
    poprawne_od_najnowszych = poprawne.sort_values("ingestion_timestamp", ascending=False, kind="stable")
    czy_duplikat = poprawne_od_najnowszych.duplicated(subset=KLUCZ, keep="first")

    wygrane = poprawne_od_najnowszych.loc[~czy_duplikat]
    duplikaty = bronze.loc[poprawne_od_najnowszych.index[czy_duplikat], kolumny_zrodlowe].sort_index()

    # --- Krok 3: Silver z wartościami znormalizowanymi i typowanymi ----------------------
    silver = (
        pd.DataFrame(
            {
                "record_id": wygrane["record_id"],
                "date": wygrane["date_norm"],
                "ticker": wygrane["ticker_norm"],
                "close": wygrane["close_num"],
                "volume": wygrane["volume_num"].astype("int64"),
                "batch_id": wygrane["batch_id"],
                "ingestion_timestamp": wygrane["ingestion_timestamp"],
            }
        )
        .sort_values(["date", "ticker"])
        .reset_index(drop=True)
    )

    # --- Zapis ---------------------------------------------------------------------------
    silver.to_csv(PLIK_SILVER, sep=SEP, index=False, encoding=KODOWANIE)
    odrzuty.to_csv(PLIK_ODRZUTY, sep=SEP, index=False, encoding=KODOWANIE)
    duplikaty.to_csv(PLIK_DUPLIKATY, sep=SEP, index=False, encoding=KODOWANIE)

    # --- Raport --------------------------------------------------------------------------
    print("Liczności:")
    print(f"  Bronze:    {len(bronze)}")
    print(f"  Silver:    {len(silver)}")
    print(f"  Odrzuty:   {len(odrzuty)}")
    print(f"  Duplikaty: {len(duplikaty)}")

    print("\nOdrzuty (powód):")
    for idx in odrzuty.index:
        print(f"  {bronze.at[idx, 'record_id']}: {powod.at[idx]}")

    print("\nDuplikaty (który rekord je zastąpił):")
    zwyciezca = wygrane.set_index(KLUCZ)
    for idx in duplikaty.index:
        klucz = (df.at[idx, "date_norm"], df.at[idx, "ticker_norm"])
        print(
            f"  {bronze.at[idx, 'record_id']} ({bronze.at[idx, 'ingestion_timestamp']}) "
            f"-> zastąpiony przez {zwyciezca.at[klucz, 'record_id']} "
            f"({zwyciezca.at[klucz, 'ingestion_timestamp']}) dla klucza {klucz}"
        )

    print("\nSilver:")
    print(silver.to_string(index=False))

    # --- Kontrole ------------------------------------------------------------------------
    print("\nKontrole:")
    bledy: list = []
    id_bronze = set(bronze["record_id"])
    id_silver = set(silver["record_id"])
    id_odrzuty = set(odrzuty["record_id"])
    id_duplikaty = set(duplikaty["record_id"])

    sprawdz(bronze["record_id"].is_unique, "record_id w Bronze jest unikalny", bledy)
    sprawdz(
        len(bronze) == len(silver) + len(odrzuty) + len(duplikaty),
        f"Bronze = Silver + odrzuty + duplikaty ({len(bronze)} = {len(silver)} + {len(odrzuty)} + {len(duplikaty)})",
        bledy,
    )
    sprawdz(
        not (id_silver & id_odrzuty or id_silver & id_duplikaty or id_odrzuty & id_duplikaty),
        "zbiory są rozłączne (żaden record_id nie trafił do dwóch zbiorów)",
        bledy,
    )
    sprawdz(id_silver | id_odrzuty | id_duplikaty == id_bronze, "każdy rekord Bronze trafił do jakiegoś zbioru", bledy)
    sprawdz(not silver.duplicated(subset=["date", "ticker"]).any(), "w Silver nie powtarza się para (date, ticker)", bledy)
    sprawdz(
        bool((silver["ticker"] == silver["ticker"].str.strip().str.upper()).all()),
        "tickery w Silver są znormalizowane",
        bledy,
    )
    sprawdz(
        bool((silver["close"] > 0).all() and (silver["volume"] >= 0).all()),
        "Silver spełnia reguły close > 0 i volume >= 0",
        bledy,
    )
    # Każdy duplikat musi być starszy od wersji, która została w Silver.
    sprawdz(
        all(
            bronze.at[idx, "ingestion_timestamp"]
            < zwyciezca.at[(df.at[idx, "date_norm"], df.at[idx, "ticker_norm"]), "ingestion_timestamp"]
            for idx in duplikaty.index
        ),
        "każdy duplikat jest starszy niż rekord, który go zastąpił w Silver",
        bledy,
    )
    # Odrzuty zapisane bajt w bajt tak jak w źródle (np. ' aapl ' ze spacjami, puste pola).
    sprawdz(
        wczytaj_bronze(PLIK_ODRZUTY).equals(odrzuty.reset_index(drop=True))
        and wczytaj_bronze(PLIK_DUPLIKATY).equals(duplikaty.reset_index(drop=True)),
        "odrzuty i duplikaty zapisano w oryginalnej postaci",
        bledy,
    )

    if bledy:
        print(f"\nNiepowodzenie: {len(bledy)} kontroli nie przeszło.")
        return 1
    print("\nWszystkie kontrole przeszły.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
