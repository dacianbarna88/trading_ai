# V19 Macro Intelligence Sources

## Source Priority

Use official or primary sources only.

## United States

### FRED / Federal Reserve Bank of St. Louis
Use for:
- Federal Funds Rate
- Treasury yields
- Yield curve
- CPI
- PCE
- Unemployment
- GDP
- Credit spreads

Priority: HIGH
API: YES
Notes: preferred aggregator for US macro time series.

### BLS
Use for:
- CPI
- Unemployment
- Payrolls
- Wages

Priority: HIGH
API: YES
Notes: official source for labor and inflation statistics.

### BEA
Use for:
- GDP
- PCE
- Personal income
- Consumption

Priority: HIGH
API: YES
Notes: official source for national accounts.

## Europe

### ECB Data Portal
Use for:
- ECB policy rates
- Euro area inflation
- Monetary aggregates
- Euro area macro data

Priority: HIGH
API: YES
Notes: official ECB statistical data portal.

## Rules

- Do not use unofficial blogs as macro source of truth.
- Do not use stale values without timestamp.
- Every macro value must store:
  - source
  - indicator
  - latest date
  - latest value
  - previous value
  - trend
  - interpretation
- If data is missing, return MISSING_DATA, not a guessed value.

## Project Flags

ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
