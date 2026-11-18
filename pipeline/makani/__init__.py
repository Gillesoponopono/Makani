"""Makani data pipeline: fetches PacIOOS WRF wind and waves and NOAA tides into static JSON."""

USER_AGENT = "Makani-forecast (+https://github.com/Gillesoponopono/Makani)"
SCHEMA_VERSION = 6  # 2: map frames, 3: tides and waves, 4: sea temperature, 5: sky, 6: NWS
