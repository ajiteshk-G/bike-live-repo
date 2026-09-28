import { VehicleItem } from "@/types";

// Offline fallback catalog for TVS Motor, generated from backend/data/brands/tvs.json.
// Used only when the backend catalog API is unreachable.
export const DEFAULT_BRAND_ID = "tvs";
export const DEFAULT_VEHICLE_ID = "tvs_apache_rtr_160_4v";
export const BIKE_PLACEHOLDER_IMAGE = "/assets/placeholder-bike.svg";

export const DEFAULT_VEHICLES: VehicleItem[] = [
  {
    "id": "tvs_apache_rtr_160_4v",
    "name": "TVS Apache RTR 160 4V",
    "tagline": "SMARTER PERFORMANCE",
    "category": "Sports Motorcycle",
    "price_range": "₹1,14,390 - ₹1,44,690",
    "hero_image": "/uploads/tvs/vehicles/tvs_apache_rtr_160_4v.png",
    "engine_specs": "159.7cc, 4-valve O3C engine, oil-cooled, SOHC, Fuel Injection, 17.55 PS, 14.73 Nm",
    "seating_capacity": "Rider + Pillion",
    "fuel_or_battery": "Petrol",
    "range_or_mileage": "",
    "key_highlights": [
      "17.55 PS power",
      "Race-tuned USD suspension",
      "Dual-channel ABS with RLP Control",
      "Class-D Projector Headlamp",
      "Advanced Traction Control System",
      "5-inch TFT cluster with Google Map Mirroring"
    ],
    "usp": "Smarter performance with RT-Fi technology, race-tuned features, and advanced connectivity via 5-inch TFT cluster.",
    "variants": [
      {
        "name": "TVS Apache RTR 160 4V (Single Channel ABS)",
        "price_ex_showroom": "₹1,14,390",
        "engine_or_battery": "159.7cc, 4-valve O3C engine",
        "transmission": "5-speed manual",
        "key_features": [
          "Telescopic Fork",
          "Single Channel ABS"
        ]
      },
      {
        "name": "TVS Apache RTR 160 4V (Dual Channel ABS with TFT Map)",
        "price_ex_showroom": "₹1,44,690",
        "engine_or_battery": "159.7cc, 4-valve O3C engine",
        "transmission": "5-speed manual",
        "key_features": [
          "Dual Channel ABS with RLP Control",
          "37mm Upside Down Suspension",
          "5-inch TFT Cluster with Google Map Mirroring",
          "Traction Control System",
          "Adjustable Levers",
          "Type-C Charger"
        ]
      }
    ],
    "source_url": "https://www.tvsmotor.com/tvs-apache/apache-rtr-160-4v",
    "displacement_cc": "159.7",
    "max_power": "17.55 PS @ 9250 rpm",
    "max_torque": "14.73 Nm @ 7500 rpm",
    "top_speed": "103 km/h (Urban/Rain mode)",
    "braking": "Dual Channel ABS With RLP Control",
    "riding_modes": [
      "Sport",
      "Urban",
      "Rain"
    ],
    "colors": [
      "Arctic Teal"
    ],
    "competitors": [
      "Bajaj Pulsar N160",
      "Hero Xtreme 160R",
      "Yamaha FZ-S FI"
    ]
  },
  {
    "id": "tvs_apache_rr_310",
    "name": "TVS Apache RR 310",
    "tagline": "High-performance 310cc sport bike",
    "category": "Supersport",
    "price_range": "₹2,66,190 - ₹3,34,440",
    "hero_image": "/uploads/tvs/vehicles/tvs_apache_rr_310.png",
    "engine_specs": "312.2cc single-cylinder liquid-cooled, 34 PS, 27.3 Nm",
    "seating_capacity": "Rider + Pillion",
    "fuel_or_battery": "Petrol",
    "range_or_mileage": "33.1 kmpl (claimed)",
    "key_highlights": [
      "312.2cc liquid-cooled reverse-inclined engine",
      "Race-tuned USD forks and monoshock",
      "Dual-channel ABS",
      "Ride Modes (Urban, Rain, Sport, Track)",
      "5-inch TFT display with SmartXonnect",
      "Slipper clutch"
    ],
    "usp": "Best 310 cc engine!",
    "variants": [
      {
        "name": "TVS Apache RR 310",
        "price_ex_showroom": "₹2,66,190",
        "engine_or_battery": "312.2cc single-cylinder liquid-cooled",
        "transmission": "6-speed manual",
        "key_features": [
          "Race-tuned USD forks",
          "Dual-channel ABS",
          "Ride Modes",
          "5-inch TFT display"
        ]
      }
    ],
    "source_url": "https://www.tvsmotor.com/tvs-apache/rr-310",
    "displacement_cc": "312.2",
    "max_power": "34 PS",
    "max_torque": "27.3 Nm",
    "kerb_weight": "174 kg",
    "seat_height": "810 mm",
    "fuel_tank_or_battery": "11 litres",
    "top_speed": "160 kmph",
    "braking": "Dual-channel ABS, 300mm front disc, 240mm rear disc",
    "riding_modes": [
      "Urban",
      "Rain",
      "Sport",
      "Track"
    ],
    "colors": [
      "Titanium Black",
      "Racing Red"
    ],
    "competitors": [
      "KTM RC 390",
      "Kawasaki Ninja 300",
      "BMW G 310 RR"
    ]
  },
  {
    "id": "tvs_ronin",
    "name": "TVS Ronin",
    "tagline": "A stylish 225 cc motorcycle that's evolved like no other.",
    "category": "Cruiser / Retro",
    "price_range": "₹1,49,200 - ₹1,72,700 (approx.)",
    "hero_image": "/uploads/tvs/vehicles/tvs_ronin.png",
    "engine_specs": "225.9cc single-cylinder oil-cooled, 20.4 PS, 19.93 Nm",
    "seating_capacity": "Rider + Pillion",
    "fuel_or_battery": "Petrol",
    "range_or_mileage": "40 kmpl (claimed)",
    "key_highlights": [
      "225.9cc Single-cylinder Engine",
      "All-LED Lighting",
      "SmartXonnect Bluetooth Connectivity",
      "USD Front Forks",
      "Assist & Slipper Clutch",
      "GTT (Glide Through Technology)"
    ],
    "usp": "Modern-retro design with advanced features and a refined engine, offering a versatile riding experience.",
    "variants": [
      {
        "name": "TVS Ronin SS",
        "price_ex_showroom": "₹1,49,200 (approx.)",
        "engine_or_battery": "225.9cc Petrol",
        "transmission": "5-speed manual",
        "key_features": [
          "Single-channel ABS",
          "All-LED lighting",
          "Digital instrument cluster"
        ]
      },
      {
        "name": "TVS Ronin DS",
        "price_ex_showroom": "₹1,56,500 (approx.)",
        "engine_or_battery": "225.9cc Petrol",
        "transmission": "5-speed manual",
        "key_features": [
          "Single-channel ABS",
          "All-LED lighting",
          "Digital instrument cluster",
          "TVS SmartXonnect"
        ]
      },
      {
        "name": "TVS Ronin TD",
        "price_ex_showroom": "₹1,72,700 (approx.)",
        "engine_or_battery": "225.9cc Petrol",
        "transmission": "5-speed manual",
        "key_features": [
          "Dual-channel ABS",
          "All-LED lighting",
          "TVS SmartXonnect",
          "USD front forks",
          "Assist & Slipper Clutch",
          "Riding Modes (Urban, Rain)"
        ]
      }
    ],
    "source_url": "https://www.tvsmotor.com/tvs-ronin",
    "displacement_cc": "225.9",
    "max_power": "20.4 PS @ 7750 rpm",
    "max_torque": "19.93 Nm @ 3750 rpm",
    "kerb_weight": "160 kg",
    "seat_height": "795 mm",
    "fuel_tank_or_battery": "14 litres",
    "top_speed": "120 km/h",
    "braking": "Disc (front & rear) with Single-channel ABS / Dual-channel ABS",
    "riding_modes": [
      "Urban",
      "Rain"
    ],
    "colors": [
      "Galactic Grey",
      "Delta Blue",
      "Stargaze Black",
      "Dawn Orange",
      "Magma Orange",
      "Lightning Black"
    ],
    "competitors": [
      "Royal Enfield Hunter 350",
      "Honda CB350RS",
      "Bajaj Avenger 220 Cruise"
    ]
  },
  {
    "id": "tvs_radeon",
    "name": "TVS Radeon",
    "tagline": "TVS Radeon with 20 Best-In-Class Features & 15% More Mileage is the best Commuter Bike in India.",
    "category": "Commuter Motorcycle",
    "price_range": "₹62,405 - ₹95,954",
    "hero_image": "/uploads/tvs/vehicles/tvs_radeon.jpg",
    "engine_specs": "109.7cc single-cylinder air-cooled, 8.08 PS, 8.7 Nm",
    "seating_capacity": "Rider + Pillion",
    "fuel_or_battery": "Petrol",
    "range_or_mileage": "69.3 kmpl (claimed)",
    "key_highlights": [
      "Real Time Mileage Display",
      "USB Charger",
      "Chrome bezel headlamp with DRL",
      "Long Lasting Dura Life Engine",
      "18” bigger wheels",
      "Highest Ground Clearance & Longest Wheel Base"
    ],
    "usp": "The perfect blend of style, performance, and safety makes the TVS Radeon an ideal choice for commuters.",
    "variants": [
      {
        "name": "TVS Radeon Base Edition (Drum)",
        "price_ex_showroom": "₹62,405",
        "engine_or_battery": "109.7cc single-cylinder air-cooled",
        "transmission": "4-speed manual",
        "key_features": [
          "Real Time Mileage Display",
          "Longest Seat",
          "Drum Brakes with SBT"
        ]
      },
      {
        "name": "TVS Radeon Dual Tone Edition (Disc)",
        "price_ex_showroom": "₹95,954",
        "engine_or_battery": "109.7cc single-cylinder air-cooled",
        "transmission": "4-speed manual",
        "key_features": [
          "Dual Tone Graphics",
          "Front Disc Brake with SBT",
          "USB Charger",
          "Chrome bezel headlamp with DRL"
        ]
      }
    ],
    "source_url": "https://www.tvsmotor.com/tvs-radeon",
    "displacement_cc": "109.7",
    "max_power": "8.08 PS @ 7350 rpm",
    "max_torque": "8.7 Nm @ 4500 rpm",
    "kerb_weight": "116 kg",
    "seat_height": "780 mm",
    "fuel_tank_or_battery": "10 litres",
    "top_speed": "90 kmph",
    "braking": "Front Disc / Drum, Rear Drum with SBT",
    "colors": [
      "Metal Black",
      "Pearl White",
      "Royal Purple",
      "Golden Beige",
      "Titanium Grey",
      "Volcano Red",
      "Dual Tone Blue & Black",
      "Dual Tone Red & Black"
    ],
    "competitors": [
      "Hero Splendor Plus",
      "Bajaj Platina 110",
      "Honda CD 110 Dream"
    ]
  },
  {
    "id": "tvs_star_city_plus",
    "name": "TVS Star City Plus",
    "tagline": "premium motorcycle with a 110cc engine, enhanced style and best-in-class features.",
    "category": "Commuter Motorcycle",
    "price_range": "₹69,600 - ₹79,600",
    "hero_image": "/uploads/tvs/vehicles/tvs_star_city_plus.jpg",
    "engine_specs": "109.7cc single-cylinder air-cooled, 8.08 PS, 8.7 Nm",
    "seating_capacity": "Rider + Pillion",
    "fuel_or_battery": "Petrol",
    "range_or_mileage": "70 kmpl (approx.)",
    "key_highlights": [
      "ETFi Technology",
      "110 cc 'Eco thurst' engine",
      "15% Higher Mileage",
      "LED Tech Headlamp",
      "Roto Petal Disc Brake",
      "SBT (Synchronized Braking Technology)"
    ],
    "usp": "only bike in the 110cc segment to have LED Tech Headlamp",
    "variants": [
      {
        "name": "TVS Star City Plus Drum",
        "price_ex_showroom": "₹69,600",
        "engine_or_battery": "109.7cc 'Eco thurst' engine",
        "transmission": "4-speed manual",
        "key_features": [
          "ETFi Technology",
          "LED Headlamp",
          "SBT"
        ]
      },
      {
        "name": "TVS Star City Plus Disc",
        "price_ex_showroom": "₹79,600",
        "engine_or_battery": "109.7cc 'Eco thurst' engine",
        "transmission": "4-speed manual",
        "key_features": [
          "ETFi Technology",
          "LED Headlamp",
          "240 mm Front Disc Brake",
          "SBT"
        ]
      }
    ],
    "source_url": "https://www.tvsmotor.com/tvs-star-city-plus",
    "displacement_cc": "110",
    "max_power": "8.08 PS",
    "max_torque": "8.7 Nm",
    "braking": "240 mm front disc brake, SBT",
    "competitors": [
      "Hero Splendor Plus",
      "Bajaj Platina 110",
      "Honda CD 110 Dream"
    ]
  },
  {
    "id": "tvs_ntorq_125",
    "name": "TVS NTORQ 125",
    "tagline": "",
    "category": "Performance Scooter",
    "price_range": "₹85,000 - ₹1,06,000 (approx.)",
    "hero_image": "/assets/placeholder-bike.svg",
    "engine_specs": "Single Cylinder, 4 - Stroke, SI, Air Cooled, Fuel Injected, 124.8 cc (3V), 7 KW @7000 RPM, 10.6 Nm @ 5500 RPM",
    "seating_capacity": "Rider + Pillion",
    "fuel_or_battery": "Petrol",
    "range_or_mileage": "47 kmpl (claimed)",
    "key_highlights": [
      "Fuel Injected 124.8cc Engine",
      "Telescopic Front Suspension",
      "Front Disc Brake option (220mm)",
      "Tubeless Tyres",
      "LED Headlamp (Race Edition)",
      "Quick Acceleration (8.9 sec)"
    ],
    "usp": "Performance-oriented 125cc engine with quick acceleration and advanced braking options.",
    "variants": [
      {
        "name": "TVS NTORQ 125 Standard",
        "price_ex_showroom": "₹85,000 (approx.)",
        "engine_or_battery": "124.8 cc, 7 KW, 10.6 Nm",
        "transmission": "CVT automatic",
        "key_features": [
          "Front Drum 130mm with SBT",
          "Telescopic Suspension",
          "Tubeless Tyres"
        ]
      },
      {
        "name": "TVS NTORQ 125 Race Edition",
        "price_ex_showroom": "₹95,000 (approx.)",
        "engine_or_battery": "124.8 cc, 7 KW, 10.6 Nm",
        "transmission": "CVT automatic",
        "key_features": [
          "Front Disc 220mm with SBT",
          "LED Headlamp",
          "Telescopic Suspension",
          "Tubeless Tyres"
        ]
      }
    ],
    "source_url": "https://www.tvsmotor.com/commuter/tvs-ntorq",
    "displacement_cc": "124.8 cc",
    "max_power": "7 KW @7000 RPM",
    "max_torque": "10.6 Nm @ 5500 RPM",
    "kerb_weight": "111 Kg",
    "seat_height": "770 mm",
    "fuel_tank_or_battery": "5.8 litre",
    "top_speed": "95 km/h",
    "braking": "Front Disc 220mm with SBT / Drum 130mm with SBT, Rear Dia Drum 130mm",
    "competitors": [
      "Honda Dio 125",
      "Suzuki Avenis 125",
      "Aprilia SR 125"
    ]
  },
  {
    "id": "tvs_jupiter_disc_smartxonnect",
    "name": "TVS Jupiter Disc SmartXonnect",
    "tagline": "The best scooter featuring ETFi technology, a digital-analogue speedometer, and exceptional comfort.",
    "category": "Scooter",
    "price_range": "₹90,441 - ₹91,591",
    "hero_image": "/assets/placeholder-bike.svg",
    "engine_specs": "113.3 cc single-cylinder, 4-stroke, 5.9KW (8.02 PS) @ 6500 rpm, 9.8 Nm @ 5000 rpm",
    "seating_capacity": "Rider + Pillion",
    "fuel_or_battery": "Petrol",
    "range_or_mileage": "50 kmpl (approx.)",
    "key_highlights": [
      "First in segment - Follow Me Headlamp",
      "Connected Navigation with voice assist",
      "TVS iGO Assist (Integrated Start Stop)",
      "External Front Fuel Fill",
      "First in segment - Emergency Brake Warning",
      "Largest underseat storage (33L)"
    ],
    "usp": "Advanced Bluetooth connectivity, digital console, LED headlamp, and front disc brake, offering a smart, safe, and stylish ride for urban commuters.",
    "variants": [
      {
        "name": "TVS Jupiter Disc SmartXonnect",
        "price_ex_showroom": "₹90,441 - ₹91,591",
        "engine_or_battery": "113.3 cc single-cylinder, 4-stroke",
        "transmission": "CVT Automatic",
        "key_features": [
          "Front Disc Brake",
          "Bluetooth connectivity",
          "Fully digital colored speedometer",
          "Voice assisted navigation",
          "Call & SMS alerts",
          "Smart mileage indicators"
        ]
      }
    ],
    "source_url": "https://www.tvsmotor.com/tvs-jupiter/jupiter-disc-smartxonnect",
    "displacement_cc": "113.3",
    "max_power": "5.9KW @ 6500 rpm",
    "max_torque": "9.8 Nm @ 5000 rpm",
    "kerb_weight": "106 Kg",
    "seat_height": "770 mm",
    "fuel_tank_or_battery": "5.8 litres",
    "braking": "Front Disc, Rear Drum with Synchronous Braking System (SBT)",
    "riding_modes": [
      "Eco",
      "Power"
    ],
    "colors": [
      "Dawn Blue Matte",
      "Galactic Copper Matte",
      "Starlight Blue Gloss"
    ],
    "competitors": [
      "Honda Activa 6G",
      "Suzuki Access 125",
      "Hero Pleasure Plus Xtec"
    ]
  },
  {
    "id": "tvs_zest_110_bs6",
    "name": "TVS Zest 110 BS6",
    "tagline": "Best Mileage Scooter in its class",
    "category": "Scooter",
    "price_range": "₹65,450 - ₹82,549",
    "hero_image": "/uploads/tvs/vehicles/tvs_zest_110_bs6.png",
    "engine_specs": "110cc Eco Thrust Engine with ETFi technology",
    "seating_capacity": "Rider + Pillion",
    "fuel_or_battery": "Petrol",
    "range_or_mileage": "15% More Mileage (claimed)",
    "key_highlights": [
      "ETFi Technology",
      "Eco Thrust Engine",
      "19L Underseat Storage",
      "Front Glove Box",
      "EaZy* Centre Stand",
      "LED Tail Lamp"
    ],
    "usp": "Best Mileage Scooter in its class",
    "variants": [
      {
        "name": "TVS Zest 110 BS6",
        "price_ex_showroom": "₹65,450 - ₹82,549",
        "engine_or_battery": "110cc Eco Thrust Engine",
        "transmission": "CVT automatic",
        "key_features": [
          "ETFi Technology",
          "Eco Thrust Engine",
          "19L Underseat Storage",
          "Front Glove Box",
          "EaZy* Centre Stand",
          "LED Tail Lamp"
        ]
      }
    ],
    "source_url": "https://www.tvsmotor.com/tvs-zest",
    "displacement_cc": "110",
    "kerb_weight": "102 kg",
    "colors": [
      "Turquoise Blue",
      "Matte Black",
      "Purple",
      "Red",
      "Yellow"
    ],
    "competitors": [
      "Honda Activa 6G",
      "Hero Pleasure+",
      "Suzuki Access 125"
    ]
  },
  {
    "id": "tvs_iqube",
    "name": "TVS iQube",
    "tagline": "Reinventing mobility solutions",
    "category": "Electric Scooter",
    "price_range": "₹94,434 - ₹1,58,834",
    "hero_image": "/uploads/tvs/vehicles/tvs_iqube.png",
    "engine_specs": "4.4 kW hub motor, 2.3 kWh to 5.3 kWh battery options",
    "seating_capacity": "Rider + Pillion",
    "fuel_or_battery": "Electric (2.3 kWh / 3.1 kWh / 3.5 kWh / 4.7 kWh / 5.3 kWh)",
    "range_or_mileage": "212 km IDC range",
    "key_highlights": [
      "0 to 40 km/h in 4.2 seconds",
      "Q-Park Assist",
      "Up to 212 km IDC range",
      "SmartXonnect connectivity",
      "Portable 950W charger",
      "3 year/50,000 kms battery warranty"
    ],
    "usp": "Ultra-low running cost of ₹0.18/km",
    "variants": [
      {
        "name": "iQube 2.3 kWh",
        "price_ex_showroom": "₹94,434",
        "engine_or_battery": "2.3 kWh battery, 4.4 kW motor",
        "transmission": "Single-speed",
        "key_features": [
          "114 km IDC range",
          "10-80% charging in 2 h 25 min",
          "Top speed 68 km/h"
        ]
      },
      {
        "name": "iQube 3.1 kWh",
        "price_ex_showroom": "₹1,00,000",
        "engine_or_battery": "3.1 kWh battery, 4.4 kW motor",
        "transmission": "Single-speed",
        "key_features": [
          "123 km IDC range",
          "10-80% charging in 3 h 30 min",
          "Top speed 82 km/h"
        ]
      },
      {
        "name": "iQube 3.5 kWh",
        "price_ex_showroom": "₹1,08,993",
        "engine_or_battery": "3.5 kWh battery, 4.4 kW motor",
        "transmission": "Single-speed",
        "key_features": [
          "145 km IDC range",
          "10-80% charging in 3 h 45 min",
          "Top speed 82 km/h"
        ]
      },
      {
        "name": "iQube MillionR Edition",
        "price_ex_showroom": "₹1,08,993",
        "engine_or_battery": "3.5 kWh battery, 4.4 kW motor",
        "transmission": "Single-speed",
        "key_features": [
          "145 km IDC range",
          "10-80% charging in 3 h 45 min",
          "Top speed 82 km/h"
        ]
      },
      {
        "name": "iQube S 4.7 kWh",
        "price_ex_showroom": "₹1,17,642",
        "engine_or_battery": "4.7 kWh battery, 4.4 kW motor",
        "transmission": "Single-speed",
        "key_features": [
          "175 km IDC range",
          "10-80% charging in 3 h 15 min",
          "Top speed 82 km/h"
        ]
      },
      {
        "name": "iQube ST 5.3 kWh",
        "price_ex_showroom": "₹1,58,834",
        "engine_or_battery": "5.3 kWh battery, 4.4 kW motor",
        "transmission": "Single-speed",
        "key_features": [
          "212 km IDC range",
          "10-80% charging in 4 h 00 min",
          "Top speed 82 km/h"
        ]
      }
    ],
    "source_url": "https://www.tvsmotor.com/electric-scooters/tvs-iqube",
    "max_power": "4.4 kW",
    "fuel_tank_or_battery": "2.3 kWh / 3.1 kWh / 3.5 kWh / 4.7 kWh / 5.3 kWh",
    "top_speed": "82 km/h",
    "riding_modes": [
      "Power Mode"
    ],
    "competitors": [
      "Ola S1 Pro",
      "Ather 450X",
      "Bajaj Chetak"
    ]
  },
  {
    "id": "tvs_orbiter_electric_scooter",
    "name": "TVS Orbiter Electric Scooter",
    "tagline": "All new TVS Orbiter electric scooter 2025 with 158 km range & 68 km/h speed. Check all about TVS Orbiter's price, specs, colour options & more. Experience this affordable e-scooter - book your test ride now!",
    "category": "Electric Scooter",
    "price_range": "₹1,03,650 - ₹1,15,000 (approx.)",
    "hero_image": "/assets/placeholder-bike.svg",
    "engine_specs": "Electric motor with 1.8 kWh (V1) / 3.1 kWh (V2) battery",
    "seating_capacity": "Rider + Pillion",
    "fuel_or_battery": "Electric (1.8 kWh / 3.1 kWh)",
    "range_or_mileage": "92 km (V1), 158 km (V2) IDC range",
    "key_highlights": [
      "Minimalistic Design",
      "Unmatched Comfort",
      "Built for Convenience",
      "SmartXonnect App connectivity",
      "600+ rigorous safety tests",
      "5 year/70000 KM extended warranty"
    ],
    "usp": "Affordable e-scooter with smart features and extended warranty",
    "variants": [
      {
        "name": "TVS Orbiter V1",
        "price_ex_showroom": "₹1,03,650",
        "engine_or_battery": "1.8 kWH battery",
        "transmission": "Single-speed",
        "key_features": [
          "92 km IDC Range",
          "0%-80% charge in 2 h 20m (with 650W Charger Included)",
          "5 year/70000 KM extended warranty"
        ]
      },
      {
        "name": "TVS Orbiter V2",
        "price_ex_showroom": "₹1,15,000 (approx.)",
        "engine_or_battery": "3.1 kWH battery",
        "transmission": "Single-speed",
        "key_features": [
          "158 km IDC Range",
          "0%-80% charge in 4 h 10m (with 650W Charger Included)",
          "0%-80% charge in 2 h 38m (with Add-On 950W Charger)",
          "5 year/70000 KM extended warranty"
        ]
      }
    ],
    "source_url": "https://www.tvsmotor.com/electric-scooters/tvs-orbiter",
    "fuel_tank_or_battery": "1.8 kWh (V1), 3.1 kWh (V2)",
    "top_speed": "68 km/h",
    "colors": [
      "Neon Sunburst",
      "Stratos Blue",
      "Martian Copper",
      "Cosmic Titanium",
      "Stellar Silver",
      "Lunar Grey"
    ],
    "competitors": [
      "Ola S1 Air",
      "Ather 450S",
      "Bajaj Chetak Urbane",
      "Vida V1 Plus"
    ]
  },
  {
    "id": "tvs_x",
    "name": "TVS X",
    "tagline": "Electric goes TVS X has arrived Born Of Thrill",
    "category": "Electric Scooter",
    "price_range": "₹ 2,66,141",
    "hero_image": "/uploads/tvs/vehicles/tvs_x.webp",
    "engine_specs": "11 kW peak power, 4.44 kWh battery",
    "seating_capacity": "Rider + Pillion",
    "fuel_or_battery": "Electric (4.44 kWh)",
    "range_or_mileage": "140 km IDC range",
    "key_highlights": [
      "All-new TVS Xleton platform with aluminium exposed frame",
      "Cutting-edge LED headlamps and lean-activated bend lamps",
      "Expansive tiltable 10.2 inch TFT Panoramic display",
      "Segment-first regen selection choice",
      "Smart Hill Hold technology",
      "Intuitive navigation system with full map view"
    ],
    "usp": "Crossover of Disciplines with Lean, Mean, Clean Design and expansive tiltable 10.2 inch TFT Panoramic display",
    "variants": [
      {
        "name": "TVS X",
        "price_ex_showroom": "₹ 2,66,141",
        "engine_or_battery": "4.44 kWh battery, 11 kW peak power",
        "transmission": "Single-speed",
        "key_features": [
          "10.2 inch TFT Panoramic display",
          "Smart Hill Hold",
          "Regen selection",
          "LED headlamps with lean-activated bend lamps",
          "Aluminium exposed frame"
        ]
      }
    ],
    "source_url": "https://www.tvsmotor.com/electric-scooters/tvs-x",
    "max_power": "11 kW",
    "fuel_tank_or_battery": "4.44 kWh",
    "top_speed": "105 Kmph",
    "riding_modes": [
      "Xtealth",
      "Xtride"
    ],
    "competitors": [
      "Ather 450X",
      "Ola S1 Pro",
      "Bajaj Chetak",
      "Vida V1 Pro"
    ]
  }
];
