"""Sector group definitions shared across research modules."""

SECTOR_GROUPS: dict[str, list[str]] = {
    "Technology": [
        "AAPL", "MSFT", "GOOGL", "GOOG", "META", "ORCL", "CRM", "ADBE", "NOW", "INTU",
        "IBM", "CSCO", "PANW", "SNPS", "CDNS", "ANET", "FTNT", "CRWD", "DDOG", "SNOW",
        "PLTR", "TEAM", "WDAY", "ADSK", "HPQ", "DELL",
    ],
    "Semiconductors": [
        "NVDA", "AMD", "INTC", "AVGO", "QCOM", "TXN", "MU", "AMAT", "LRCX", "KLAC",
        "MRVL", "ON", "ADI", "NXPI", "MCHP", "MPWR", "SWKS", "QRVO", "TER", "ENTG",
    ],
    "Financials": [
        "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "AXP", "V", "MA", "COF",
        "USB", "PNC", "TFC", "BK", "STT", "CB", "MMC", "AIG", "MET", "PRU", "ALL",
        "TRV", "AFL", "CME", "ICE", "SPGI", "MCO",
    ],
    "Industrials": [
        "CAT", "DE", "HON", "GE", "RTX", "LMT", "BA", "UPS", "FDX", "UNP", "CSX",
        "NSC", "WM", "RSG", "EMR", "ETN", "ITW", "PH", "ROK", "CMI", "PCAR", "GD",
        "NOC", "JCI", "TT", "FAST",
    ],
    "Healthcare": [
        "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "DHR", "BMY", "AMGN",
        "GILD", "VRTX", "REGN", "ISRG", "SYK", "BSX", "MDT", "ELV", "CI", "HUM",
        "CVS", "MCK", "ZTS", "BDX", "EW", "IDXX", "DXCM", "HCA",
    ],
    "Consumer": [
        "PG", "KO", "PEP", "WMT", "COST", "HD", "LOW", "MCD", "NKE", "SBUX", "TGT",
        "TJX", "ROST", "DG", "DLTR", "YUM", "CMG", "BKNG", "MAR", "HLT", "ORLY",
        "AZO", "F", "GM", "RIVN", "LULU", "EL", "CL", "KMB", "GIS", "KHC",
    ],
    "Energy": [
        "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HES",
        "DVN", "HAL", "BKR", "KMI", "WMB", "OKE", "TRGP", "FANG", "APA",
    ],
    "Communications": [
        "DIS", "NFLX", "CMCSA", "T", "VZ", "TMUS", "CHTR", "WBD", "OMC", "IPG",
        "EA", "TTWO", "LYV", "MTCH",
    ],
    "Utilities": [
        "NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "ED", "WEC",
        "ES", "AWK", "PEG", "DTE", "FE", "ETR", "AEE", "CMS", "NI",
    ],
}
