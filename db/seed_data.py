"""Seeds job_codes and imagery_catalog tables from the Excel data."""
from db.database import get_connection

JOB_CODES = [
    ("Data Scientist 2", 150, 125),
    ("Analyst 3 - Imagery", 150, 125),
    ("Analyst 2 - Imagery", 120, 100),
    ("Analyst 1 - Imagery", 90, 75),
    ("Analyst 3 - GeoINT", 144, 120),
    ("Analyst 2 - GeoINT", 120, 100),
    ("Analyst 1 - GeoINT", 90, 75),
    ("Data Manager 1", 90, 75),
    ("OSINT 2", 120, 100),
    ("Contract PAI", 120, 120),
]

# (provider, description, min_area_km2, resolution, pricing_guidance, list_price, sh_price)
IMAGERY_CATALOG = [
    ("ICEYE", "Spot (SRT Partner)", 25, "1 m", "$1,085 per scene", 940, 1128),
    ("ICEYE", "Spot Fine 5-look (SRT Partner)", 25, "0.5 m", "$1,650 per scene", 1650, 1980),
    ("ICEYE", "Spot Extended Area (SRT Partner)", 225, "1 m", "$1,875 per scene", 1685, 2022),
    ("ICEYE", "Dwell (SRT Partner)", 25, "1 m", "$2,450 per scene", 1615, 1938),
    ("ICEYE", "Dwell Fine 10-look (SRT Partner)", 25, "0.5 m", "$2,750 per scene", 2625, 3150),
    ("ICEYE", "Dwell Precise (SRT Partner)", 25, "0.25m", "$2,815 per scene", 2815, 3378),
    ("ICEYE", "Strip (SRT Partner)", 1500, "3 m", "$860 per scene", 860, 1032),
    ("ICEYE", "Scan (SRT Partner)", 10000, "15 m", "$780 per scene", 780, 936),
    ("ICEYE", "GTR tasking (24-hr, standard price)", None, "mode-dependent", "$3,750 per scene", 3750, 4500),
    ("ICEYE", "Archive imagery (any mode)", None, "mode-dependent", "$450 per scene", 450, 540),
    ("Vantor (Maxar)", "30 cm Select Plus High Demand", 50, "0.30 m", "$54.5 per km^2", 2725, 3406.25),
    ("Vantor (Maxar)", "30 cm Select High Demand", 50, "0.30 m", "$32.5 per km^2", 1626.95, 2033.69),
    ("Vantor (Maxar)", "Archive 2-90 days", 25, "0.30 m", "$8.5 per km^2", 212.5, 265.63),
    ("Satellogic", "Archive Orders", 16, "n/a", "$4 per km^2", 64, 80),
    ("Satellogic", "Standard Area Coverage", 50, "0.70 m", "$8 per km^2", 400, 500),
    ("Satellogic", "Standard Tasking over POIs", 25, "0.70 m", "$10 per km^2", 250, 312.5),
    ("Satellogic", "Rush Tasking over POIs", 25, "0.70 m", "$23 per km^2", 575, 718.75),
    ("BlackSky", "Single-frame daytime - archive image (Gen-2)", 25, "0.8 m", "$100 per product", 100, 125),
    ("BlackSky", "Single-frame daytime - Standard priority tasking (Gen-2)", 25, "0.8 m", "$192 per product", 192, 240),
    ("BlackSky", "Single-frame daytime - Preferred priority tasking (Gen-2)", 25, "0.8 m", "$486 per product", 486, 607.5),
    ("BlackSky", "Single-frame daytime - Elite priority tasking (Gen-2)", 25, "0.8 m", "$1250 per product", 1250, 1562.5),
    ("BlackSky", "Single-frame nighttime - archive image (Gen-2)", 25, "0.8 m", "$100 per product", 100, 125),
    ("BlackSky", "Single-frame nighttime - Standard priority tasking (Gen-2)", 25, "0.8 m", "$192 per product", 192, 240),
    ("BlackSky", "Single-frame nighttime - Preferred priority tasking (Gen-2)", 25, "0.8 m", "$486 per product", 486, 607.5),
    ("BlackSky", "Single-frame nighttime - Elite priority tasking (Gen-2)", 25, "0.8 m", "$1250 per product", 1250, 1562.5),
    ("BlackSky", "Area 2x1 (multi-frame) - archive image (Gen-2)", 50, "0.8 m", "$160 per product", 160, 200),
    ("BlackSky", "Area 2x1 (multi-frame) - Standard priority tasking (Gen-2)", 50, "0.8 m", "$307 per product", 307, 383.75),
    ("BlackSky", "Area 2x1 (multi-frame) - Preferred priority tasking (Gen-2)", 50, "0.8 m", "$778 per product", 778, 972.5),
    ("BlackSky", "Area 2x1 (multi-frame) - Elite priority tasking (Gen-2)", 50, "0.8 m", "$2000 per product", 2000, 2500),
    ("BlackSky", "Burst (multi-frame) - archive image (Gen-2)", 25, "0.8 m", "$220 per product", 220, 275),
    ("BlackSky", "Burst (multi-frame) - Standard priority tasking (Gen-2)", 25, "0.8 m", "$420 per product", 420, 525),
    ("BlackSky", "Burst (multi-frame) - Preferred priority tasking (Gen-2)", 25, "0.8 m", "$1260 per product", 1260, 1575),
    ("BlackSky", "Burst (multi-frame) - Elite priority tasking (Gen-2)", 25, "0.8 m", "$3240 per product", 3240, 4050),
    ("BlackSky", "2-frame stereo - archive image (Gen-2)", 25, "0.8 m", "$270 per product", 270, 337.5),
    ("BlackSky", "2-frame stereo - Standard priority tasking (Gen-2)", 25, "0.8 m", "$520 per product", 520, 650),
    ("BlackSky", "2-frame stereo - Preferred priority tasking (Gen-2)", 25, "0.8 m", "$1480 per product", 1480, 1850),
    ("BlackSky", "2-frame stereo - Elite priority tasking (Gen-2)", 25, "0.8 m", "$3810 per product", 3810, 4762.5),
    ("BlackSky", "5-frame stereo - archive image (Gen-2)", 25, "0.8 m", "$310 per product", 310, 387.5),
    ("BlackSky", "5-frame stereo - Standard priority tasking (Gen-2)", 25, "0.8 m", "$590 per product", 590, 737.5),
    ("BlackSky", "5-frame stereo - Preferred priority tasking (Gen-2)", 25, "0.8 m", "$1780 per product", 1780, 2225),
    ("BlackSky", "5-frame stereo - Elite priority tasking (Gen-2)", 25, "0.8 m", "$4580 per product", 4580, 5725),
    ("BlackSky", "Single-frame daytime - Standard priority tasking (Gen-3)", 25, "0.35 m", "$1,000 per product", 1000, 1250),
    ("BlackSky", "Single-frame daytime - Preferred priority tasking (Gen-3)", 25, "0.35 m", "$2,500 per product", 2500, 3125),
    ("BlackSky", "Single-frame daytime - Elite priority tasking (Gen-3)", 25, "0.35 m", "$6,000 per product", 6000, 7500),
    ("SkyFi", "Super High Resolution 0.16-0.30 m - existing image (daytime optical)", 5, "0.16-0.30 m", "$22.50-$35 per km^2", 175, 218.75),
    ("SkyFi", "Super High Resolution 0.16-0.30 m - new image (daytime optical)", 25, "0.16-0.30 m", "$30 per km^2", 750, 937.5),
    ("SkyFi", "Super High Resolution 0.16-0.30 m - priority surcharge", 25, "0.16-0.30 m", "$55 per km^2", 55, 68.75),
    ("SkyFi", "Very High Resolution 0.31-0.50 m - existing image (daytime optical)", 5, "0.31-0.50 m", "$8 per km^2", 40, 50),
    ("SkyFi", "Very High Resolution 0.31-0.50 m - new image (daytime optical)", 25, "0.31-0.50 m", "$12 per km^2", 300, 375),
    ("SkyFi", "Very High Resolution 0.31-0.50 m - priority surcharge", 25, "0.31-0.50 m", "$24 per km^2", 600, 750),
    ("SkyFi", "Very High Resolution (Assured) 0.31-0.50 m - new image", 25, "0.31-0.50 m", "$1,000 per scene", 1000, 1250),
    ("SkyFi", "Very High Resolution (Assured) 0.31-0.50 m - priority surcharge", 25, "0.31-0.50 m", "$1,500 per scene", 1500, 1875),
    ("SkyFi", "High Resolution 0.51-1.0 m - existing image (daytime optical)", 5, "0.51-1.0 m", "$5 per km^2", 25, 31.25),
    ("SkyFi", "High Resolution 0.51-1.0 m - new image (daytime optical)", 25, "0.51-1.0 m", "$8 per km^2", 200, 250),
    ("SkyFi", "High Resolution 0.51-1.0 m - priority surcharge", 25, "0.51-1.0 m", "$12 per km^2", 300, 375),
    ("SkyFi", "Ultra High Resolution 0.075-0.10 m - existing image", 1, "0.075-0.10 m", "$100-$115 per km^2", 115, 143.75),
    ("SkyFi", "Ultra High Resolution 0.11-0.15 m - existing image", 1, "0.11-0.15 m", "$35 per km^2", 35, 43.75),
    ("SkyFi", "Stereo Super High Resolution 0.16-0.30 m - new image", 25, "0.16-0.30 m", "$60 per km^2", 1500, 1875),
    ("SkyFi", "Stereo Super High Resolution 0.16-0.30 m - priority surcharge", 25, "0.16-0.30 m", "$110 per km^2", 2750, 3437.5),
    ("SkyFi", "Stereo Very High Resolution 0.31-0.50 m - new image", 25, "0.31-0.50 m", "$24 per km^2", 600, 750),
    ("SkyFi", "Stereo Very High Resolution 0.31-0.50 m - priority surcharge", 25, "0.31-0.50 m", "$48 per km^2", 1200, 1500),
    ("SkyFi", "Tri-stereo Super High Resolution 0.16-0.30 m - new image", 25, "0.16-0.30 m", "$90 per km^2", 2250, 2812.5),
    ("SkyFi", "Tri-stereo Super High Resolution 0.16-0.30 m - priority surcharge", 25, "0.16-0.30 m", "$270 per km^2", 6750, 8437.5),
    ("SkyFi", "Tri-stereo Very High Resolution 0.31-0.50 m - new image", 25, "0.31-0.50 m", "$36 per km^2", 900, 1125),
    ("SkyFi", "Tri-stereo Very High Resolution 0.31-0.50 m - priority surcharge", 25, "0.31-0.50 m", "$180 per km^2", 4500, 5625),
    ("SkyFi", "Umbra SAR - Ultra High 0.25 m Spotlight", 25, "0.25 m", "$3,250 per scene", 3250, 4062.5),
    ("SkyFi", "Umbra SAR - Super High 0.31-0.40 m Spotlight", 25, "0.31-0.40 m", "$1,750 per scene", 1750, 2187.5),
    ("SkyFi", "Umbra SAR - Very High 0.41-0.50 m Spotlight", 25, "0.41-0.50 m", "$950 per scene", 950, 1187.5),
    ("SkyFi", "Umbra SAR - High 0.51-1.0 m Spotlight", 25, "0.51-1.0 m", "$675 per scene", 675, 843.75),
    ("SkyFi", "Umbra SAR - Ultra High 0.25 m NFP", 25, "0.25 m", "$3,750 per scene", 3750, 4687.5),
    ("SkyFi", "Umbra SAR - Super High 0.31-0.40 m NFP", 25, "0.31-0.40 m", "$2,650 per scene", 2650, 3312.5),
    ("SkyFi", "Umbra SAR - Very High 0.41-0.50 m NFP", 25, "0.41-0.50 m", "$1,900 per scene", 1900, 2375),
    ("SkyFi", "Umbra SAR - High 0.51-1.0 m NFP", 25, "0.51-1.0 m", "$1,500 per scene", 1500, 1875),
    ("SkyFi", "Umbra SAR multi-look - Ultra High 0.25 m Spotlight 2-look", 25, "0.25 m", "$4050 per scene", 4050, 5062.5),
    ("SkyFi", "Umbra SAR multi-look - Ultra High 0.25 m Spotlight 3-look", 25, "0.25 m", "$4900 per scene", 4900, 6125),
    ("SkyFi", "Umbra SAR multi-look - Super High 0.31-0.40 m Spotlight 2-look", 25, "0.31-0.40 m", "$2200 per scene", 2200, 2750),
    ("SkyFi", "Umbra SAR multi-look - Super High 0.31-0.40 m Spotlight 3-look", 25, "0.31-0.40 m", "$2650 per scene", 2650, 3312.5),
    ("SkyFi", "Umbra SAR multi-look - Super High 0.31-0.40 m Spotlight 4-look", 25, "0.31-0.40 m", "$3050 per scene", 3050, 3812.5),
    ("SkyFi", "Umbra SAR multi-look - Super High 0.31-0.40 m Spotlight 5-look", 25, "0.31-0.40 m", "$3500 per scene", 3500, 4375),
    ("SkyFi", "Umbra SAR multi-look - Very High 0.41-0.50 m Spotlight 2-look", 25, "0.41-0.50 m", "$1200 per scene", 1200, 1500),
    ("SkyFi", "Umbra SAR multi-look - Very High 0.41-0.50 m Spotlight 3-look", 25, "0.41-0.50 m", "$1400 per scene", 1400, 1750),
    ("SkyFi", "Umbra SAR multi-look - Very High 0.41-0.50 m Spotlight 4-look", 25, "0.41-0.50 m", "$1650 per scene", 1650, 2062.5),
    ("SkyFi", "Umbra SAR multi-look - Very High 0.41-0.50 m Spotlight 5-look", 25, "0.41-0.50 m", "$1900 per scene", 1900, 2375),
    ("SkyFi", "Umbra SAR multi-look - Very High 0.41-0.50 m Spotlight 8-look", 25, "0.41-0.50 m", "$2600 per scene", 2600, 3250),
    ("SkyFi", "Umbra SAR multi-look - High 0.51-1.0 m Spotlight 2-look", 25, "0.51-1.0 m", "$850 per scene", 850, 1062.5),
    ("SkyFi", "Umbra SAR multi-look - High 0.51-1.0 m Spotlight 3-look", 25, "0.51-1.0 m", "$1000 per scene", 1000, 1250),
    ("SkyFi", "Umbra SAR multi-look - High 0.51-1.0 m Spotlight 4-look", 25, "0.51-1.0 m", "$1200 per scene", 1200, 1500),
    ("SkyFi", "Umbra SAR multi-look - High 0.51-1.0 m Spotlight 5-look", 25, "0.51-1.0 m", "$1350 per scene", 1350, 1687.5),
    ("SkyFi", "Umbra SAR multi-look - High 0.51-1.0 m Spotlight 8-look", 25, "0.51-1.0 m", "$1850 per scene", 1850, 2312.5),
    ("SkyFi", "Umbra SAR multi-look - High 0.51-1.0 m Spotlight 10-look", 25, "0.51-1.0 m", "$2200 per scene", 2200, 2750),
    ("SkyFi", "Umbra SAR multi-look - Ultra High 0.25 m NFP 2-look", 25, "0.25 m", "$4700 per scene", 4700, 5875),
    ("SkyFi", "Umbra SAR multi-look - Ultra High 0.25 m NFP 3-look", 25, "0.25 m", "$5650 per scene", 5650, 7062.5),
    ("SkyFi", "Umbra SAR multi-look - Super High 0.31-0.40 m NFP 2-look", 25, "0.31-0.40 m", "$3300 per scene", 3300, 4125),
    ("SkyFi", "Umbra SAR multi-look - Super High 0.31-0.40 m NFP 3-look", 25, "0.31-0.40 m", "$4000 per scene", 4000, 5000),
    ("SkyFi", "Umbra SAR multi-look - Super High 0.31-0.40 m NFP 4-look", 25, "0.31-0.40 m", "$4650 per scene", 4650, 5812.5),
    ("SkyFi", "Umbra SAR multi-look - Super High 0.31-0.40 m NFP 5-look", 25, "0.31-0.40 m", "$5300 per scene", 5300, 6625),
    ("SkyFi", "Umbra SAR multi-look - Very High 0.41-0.50 m NFP 2-look", 25, "0.41-0.50 m", "$2400 per scene", 2400, 3000),
    ("SkyFi", "Umbra SAR multi-look - Very High 0.41-0.50 m NFP 3-look", 25, "0.41-0.50 m", "$2850 per scene", 2850, 3562.5),
    ("SkyFi", "Umbra SAR multi-look - Very High 0.41-0.50 m NFP 4-look", 25, "0.41-0.50 m", "$3350 per scene", 3350, 4187.5),
    ("SkyFi", "Umbra SAR multi-look - Very High 0.41-0.50 m NFP 5-look", 25, "0.41-0.50 m", "$3800 per scene", 3800, 4750),
    ("SkyFi", "Umbra SAR multi-look - Very High 0.41-0.50 m NFP 8-look", 25, "0.41-0.50 m", "$5250 per scene", 5250, 6562.5),
    ("SkyFi", "Umbra SAR multi-look - High 0.51-1.0 m NFP 2-look", 25, "0.51-1.0 m", "$1900 per scene", 1900, 2375),
    ("SkyFi", "Umbra SAR multi-look - High 0.51-1.0 m NFP 3-look", 25, "0.51-1.0 m", "$2250 per scene", 2250, 2812.5),
    ("SkyFi", "Umbra SAR multi-look - High 0.51-1.0 m NFP 4-look", 25, "0.51-1.0 m", "$2650 per scene", 2650, 3312.5),
    ("SkyFi", "Umbra SAR multi-look - High 0.51-1.0 m NFP 5-look", 25, "0.51-1.0 m", "$3000 per scene", 3000, 3750),
    ("SkyFi", "Umbra SAR multi-look - High 0.51-1.0 m NFP 8-look", 25, "0.51-1.0 m", "$4150 per scene", 4150, 5187.5),
    ("SkyFi", "Umbra SAR multi-look - High 0.51-1.0 m NFP 10-look", 25, "0.51-1.0 m", "$4900 per scene", 4900, 6125),
    ("SkyFi", "ICEYE SAR via SkyFi - Very High 0.50 m Dwell Fine 10-look - existing image", 25, "0.50 m", "$450 per scene", 450, 562.5),
    ("SkyFi", "ICEYE SAR via SkyFi - Very High 0.50 m Dwell Fine 10-look - new image", 25, "0.50 m", "$3,675 per scene", 3675, 4593.75),
    ("SkyFi", "ICEYE SAR via SkyFi - Very High 0.50 m Spot Fine 5-look - existing image", 25, "0.50 m", "$450 per scene", 450, 562.5),
    ("SkyFi", "ICEYE SAR via SkyFi - Very High 0.50 m Spot Fine 5-look - new image", 25, "0.50 m", "$2,200 per scene", 2200, 2750),
    ("SkyFi", "ICEYE SAR via SkyFi - High 1.0 m Dwell - existing image", 25, "1.0 m", "$450 per scene", 450, 562.5),
    ("SkyFi", "ICEYE SAR via SkyFi - High 1.0 m Dwell - new image", 25, "1.0 m", "$3,275 per scene", 3275, 4093.75),
    ("SkyFi", "ICEYE SAR via SkyFi - High 1.0 m Spot - existing image", 25, "1.0 m", "$450 per scene", 450, 562.5),
    ("SkyFi", "ICEYE SAR via SkyFi - High 1.0 m Spot - new image", 25, "1.0 m", "$1,450 per scene", 1450, 1812.5),
    ("SkyFi", "ICEYE SAR via SkyFi - High 1.0 m SLEA 15x15 km - existing image", 225, "1.0 m", "$450 per scene", 450, 562.5),
    ("SkyFi", "ICEYE SAR via SkyFi - High 1.0 m SLEA 15x15 km - new image", 225, "1.0 m", "$2,500 per scene", 2500, 3125),
    ("SkyFi", "ICEYE SAR via SkyFi - Medium 3.0 m Strip 50x30 km - existing image", 1500, "3.0 m", "$450 per scene", 450, 562.5),
    ("SkyFi", "ICEYE SAR via SkyFi - Medium 3.0 m Strip 50x30 km - new image", 1500, "3.0 m", "$1,150 per scene", 1150, 1437.5),
    ("SkyFi", "ICEYE SAR via SkyFi - Low 15 m Scan 100x100 km - existing image", 10000, "15 m", "$450 per scene", 450, 562.5),
    ("SkyFi", "ICEYE SAR via SkyFi - Low 15 m Scan 100x100 km - new image", 10000, "15 m", "$1,050 per scene", 1050, 1312.5),
    ("SkyFi", "ICEYE SAR via SkyFi - GTR 24-hr - new image", None, "Scene Dependant", "$3,750 per scene", 3750, 4687.5),
    ("Wolverine Radar", "Change Detection", 50, "15 per month", "sq/km*images*$3 = One month Change detection", 1500, 2250),
]


def seed_job_codes():
    conn = get_connection()
    existing = conn.execute("SELECT COUNT(*) FROM job_codes").fetchone()[0]
    if existing == 0:
        conn.executemany(
            "INSERT INTO job_codes (title, bid_rate, employee_rate) VALUES (?, ?, ?)",
            JOB_CODES,
        )
        conn.commit()
        print(f"Seeded {len(JOB_CODES)} job codes")
    else:
        print(f"Job codes already seeded ({existing} rows)")
    conn.close()


def seed_imagery_catalog():
    conn = get_connection()
    existing = conn.execute("SELECT COUNT(*) FROM imagery_catalog").fetchone()[0]
    if existing == 0:
        conn.executemany(
            "INSERT INTO imagery_catalog (provider, description, min_area_km2, resolution, pricing_guidance, list_price, sh_price) VALUES (?, ?, ?, ?, ?, ?, ?)",
            IMAGERY_CATALOG,
        )
        conn.commit()
        print(f"Seeded {len(IMAGERY_CATALOG)} imagery catalog entries")
    else:
        print(f"Imagery catalog already seeded ({existing} rows)")
    conn.close()


def seed_day_rate_options():
    conn = get_connection()
    existing = conn.execute("SELECT COUNT(*) FROM day_rate_options").fetchone()[0]
    if existing == 0:
        conn.execute(
            "INSERT INTO day_rate_options (total_exercised, total_used, additional_options) VALUES (?, ?, ?)",
            (36, 36, 1),
        )
        conn.commit()
        print("Seeded day rate options")
    else:
        print("Day rate options already seeded")
    conn.close()


def seed_revenue_streams():
    conn = get_connection()
    existing = conn.execute("SELECT COUNT(*) FROM revenue_streams").fetchone()[0]
    if existing == 0:
        conn.execute(
            "INSERT INTO revenue_streams (diamond_money, diamond_weeks, athena_billed, sourced_total) VALUES (?, ?, ?, ?)",
            (0, 0, 0, 0),
        )
        conn.commit()
        print("Seeded revenue streams")
    else:
        print("Revenue streams already seeded")
    conn.close()


def seed_all():
    seed_job_codes()
    seed_imagery_catalog()
    seed_day_rate_options()
    seed_revenue_streams()


if __name__ == "__main__":
    from db.database import init_db
    init_db()
    seed_all()
