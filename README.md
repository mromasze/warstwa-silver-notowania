# Warstwa Silver — notowania

Zadanie domowe: budowa warstwy Silver z surowych danych Bronze w pandas.

Skrypt `silver.py` wczytuje `bronze_notowania.csv` (20 rekordów z dwóch partii, `;`, UTF-8 z BOM), waliduje i normalizuje rekordy, usuwa duplikaty po kluczu `(date, ticker)` i zapisuje trzy zbiory:

| Plik | Zawartość | Liczność |
|---|---|---|
| `silver_notowania.csv` | poprawne, znormalizowane, unikalne notowania | 10 |
| `odrzuty.csv` | błędne rekordy w oryginalnej postaci | 8 |
| `duplikaty.csv` | starsze poprawne wersje w oryginalnej postaci | 2 |

## Uruchomienie

```bash
pip install pandas numpy
python silver.py
```

Skrypt wypisuje liczności, powody odrzuceń i kontrole (Bronze = Silver + odrzuty + duplikaty, rozłączność zbiorów, unikalność `(date, ticker)` w Silver). Gdy któraś kontrola nie przejdzie, kończy się kodem 1.

## Kolejność przetwarzania

1. Odczyt wszystkich pól jako tekst (`dtype=str`, `keep_default_na=False`), żeby zachować oryginał.
2. Normalizacja tickera (`strip` + `upper`) i parsowanie daty oraz liczb w kolumnach pomocniczych.
3. Walidacja: data, niepusty ticker, `close` skończone i > 0, `volume` skończone, całkowite i >= 0.
4. Odrzucenie błędnych rekordów, **dopiero potem** deduplikacja wśród poprawnych (najnowszy `ingestion_timestamp` wygrywa), więc nowszy błędny rekord nie wypiera starszego poprawnego.
