"""MGRS coordinate conversion utilities (WGS84, no external dependency)."""
import math


def decode(mgrs: str):
    """Parse an MGRS string to (easting, northing, zone, band)."""
    mgrs = mgrs.strip().replace(" ", "").upper()
    if len(mgrs) < 7:
        raise ValueError(f"MGRS string too short: '{mgrs}'")

    zone = int(mgrs[:2])
    band = mgrs[2]
    square_id = mgrs[3:5]
    remainder = mgrs[5:]

    if not square_id.isalpha():
        raise ValueError(f"Invalid grid square in MGRS: '{mgrs}'")

    easting_letters  = ["ABCDEFGH", "JKLMNPQR", "STUVWXYZ"]
    northing_letters = ["ABCDEFGHJKLMNPQRSTUV", "FGHJKLMNPQRSTUVABCDE"]

    col_set = (zone - 1) % 3
    row_set = (zone - 1) % 2

    e_idx = easting_letters[col_set].find(square_id[0])
    n_idx = northing_letters[row_set].find(square_id[1])
    if e_idx == -1 or n_idx == -1:
        raise ValueError(f"Invalid grid square ID: '{square_id}'")

    e100k = (e_idx + 1) * 100_000
    n100k = n_idx * 100_000

    precision = len(remainder) // 2
    easting  = e100k + int(remainder[:precision].ljust(5, "0"))
    northing = n100k + int(remainder[precision:].ljust(5, "0"))

    if band < "N":
        northing += 10_000_000

    return easting, northing, zone, band


def utm_to_latlon(utm) -> tuple:
    """Convert (easting, northing, zone, band) to (lat, lon) in decimal degrees."""
    easting, northing, zone_number, band_letter = utm

    k0 = 0.9996
    a  = 6_378_137.0
    e  = 0.081_819_191
    e1sq = 0.006_739_497

    x = easting - 500_000.0
    y = northing
    if band_letter < "N":
        y -= 10_000_000.0

    m  = y / k0
    mu = m / (a * (1 - e**2/4 - 3*e**4/64 - 5*e**6/256))

    e1 = (1 - math.sqrt(1 - e**2)) / (1 + math.sqrt(1 - e**2))
    fp = (mu
          + (3*e1/2 - 27*e1**3/32)         * math.sin(2*mu)
          + (21*e1**2/16 - 55*e1**4/32)    * math.sin(4*mu)
          + (151*e1**3/96)                  * math.sin(6*mu)
          + (1097*e1**4/512)                * math.sin(8*mu))

    c1 = e1sq * math.cos(fp)**2
    t1 = math.tan(fp)**2
    r1 = a * (1 - e**2) / (1 - e**2 * math.sin(fp)**2) ** 1.5
    n1 = a / math.sqrt(1 - e**2 * math.sin(fp)**2)
    d  = x / (n1 * k0)

    lat = fp - (n1 * math.tan(fp) / r1) * (
        d**2/2
        - (5 + 3*t1 + 10*c1 - 4*c1**2 - 9*e1sq)                          * d**4/24
        + (61 + 90*t1 + 298*c1 + 45*t1**2 - 252*e1sq - 3*c1**2)           * d**6/720
    )

    lon = (
        d
        - (1 + 2*t1 + c1)                                                  * d**3/6
        + (5 - 2*c1 + 28*t1 - 3*c1**2 + 8*e1sq + 24*t1**2)                * d**5/120
    ) / math.cos(fp)

    lat = math.degrees(lat)
    lon = (zone_number - 1) * 6 - 180 + 3 + math.degrees(lon)
    return lat, lon


def mgrs_to_latlon(mgrs_string: str) -> tuple:
    """Convert an MGRS string to (lat, lon). Raises ValueError on bad input."""
    return utm_to_latlon(decode(mgrs_string.strip().upper()))
