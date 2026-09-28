-- ==============================================================================
-- Two-Wheeler Demo (TVS Motor + Hero MotoCorp) Dealerships, Public Holidays & Test-Ride Timings Seed
-- Generic demo 'Authorised Dealer' showrooms. No customers / bookings / PII are seeded.
-- Canonical source: seeds/seed_dealerships.py (re-runnable). Keep both in sync.
-- ==============================================================================

-- 1. Dealerships Table
CREATE TABLE IF NOT EXISTS dealerships (
    id VARCHAR(64) PRIMARY KEY,
    brand_id VARCHAR(64) NOT NULL DEFAULT 'tvs',
    name VARCHAR(128) NOT NULL,
    city VARCHAR(64) NOT NULL,
    state VARCHAR(64) NOT NULL,
    area VARCHAR(128),
    address TEXT NOT NULL,
    pin_code VARCHAR(16) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    email VARCHAR(128),
    map_url VARCHAR(256),
    rating FLOAT DEFAULT 4.8,
    available_advisors JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Public Holidays Table (Stored in Database)
CREATE TABLE IF NOT EXISTS public_holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    holiday_date VARCHAR(16) UNIQUE NOT NULL,
    holiday_name VARCHAR(128) NOT NULL,
    state VARCHAR(64) DEFAULT 'ALL',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Slot Configurations Table (9:00 AM - 6:00 PM Stored in Database)
CREATE TABLE IF NOT EXISTS slot_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_time VARCHAR(32) UNIQUE NOT NULL,
    display_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Test Drive Slots (Reserved Slots in Database)
CREATE TABLE IF NOT EXISTS test_drive_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_date VARCHAR(32) NOT NULL,
    slot_time VARCHAR(32) NOT NULL,
    dealership_id VARCHAR(64) DEFAULT NULL,
    vehicle_id VARCHAR(64),
    status VARCHAR(32) DEFAULT 'AVAILABLE',
    customer_id INTEGER,
    customer_name VARCHAR(128),
    customer_phone VARCHAR(32),
    booking_reference VARCHAR(64),
    booking_type VARCHAR(32) DEFAULT 'HOME_DOORSTEP',
    delivery_address TEXT,
    pin_code VARCHAR(16),
    notes TEXT,
    reserved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SEED PUBLIC HOLIDAYS (2026 Indian Gazetted Holidays)
INSERT OR IGNORE INTO public_holidays (holiday_date, holiday_name, state) VALUES
('2026-01-26', 'Republic Day', 'ALL'),
('2026-03-03', 'Holi (Festival of Colours)', 'ALL'),
('2026-03-20', 'Eid-ul-Fitr', 'ALL'),
('2026-04-14', 'Dr. Ambedkar Jayanti', 'ALL'),
('2026-05-01', 'Maharashtra Day / May Day', 'Maharashtra'),
('2026-08-15', 'Independence Day', 'ALL'),
('2026-09-04', 'Janmashtami', 'ALL'),
('2026-10-02', 'Mahatma Gandhi Jayanti', 'ALL'),
('2026-10-20', 'Dussehra (Vijayadashami)', 'ALL'),
('2026-11-08', 'Diwali (Deepavali)', 'ALL'),
('2026-11-09', 'Govardhan Puja', 'ALL'),
('2026-11-24', 'Guru Nanak Jayanti', 'ALL'),
('2026-12-25', 'Christmas Day', 'ALL');

-- SEED OPERATIONAL TEST-RIDE TIME SLOTS (9:00 AM - 6:00 PM)
INSERT OR IGNORE INTO slot_configs (slot_time, display_order) VALUES
('09:00 AM', 1),
('10:00 AM', 2),
('11:00 AM', 3),
('12:00 PM', 4),
('01:00 PM', 5),
('02:00 PM', 6),
('03:00 PM', 7),
('04:00 PM', 8),
('05:00 PM', 9);

-- SEED DEALERSHIPS: TVS MOTOR + HERO MOTOCORP
INSERT OR REPLACE INTO dealerships (id, brand_id, name, city, state, area, address, pin_code, phone, email, map_url, rating, available_advisors) VALUES
('tvs_mumbai_andheri', 'tvs', 'TVS Motor Authorised Dealer – Andheri West', 'Mumbai', 'Maharashtra', 'Andheri West', 'Shop 4-6, Veera Desai Road, Near Azad Nagar Metro, Andheri West, Mumbai', '400053', '+91 22 4000 1101', 'tvs.mumbai.andheri@dealer-demo.in', 'https://maps.google.com/?q=TVS+Motor+Authorised+Dealer+Andheri+West', 4.7, '["Rahul Nair (Sales Consultant)", "Sneha Kulkarni (EV Specialist)"]'),
('tvs_pune_kothrud', 'tvs', 'TVS Motor Authorised Dealer – Kothrud', 'Pune', 'Maharashtra', 'Kothrud', 'Plot 21, Paud Road, Near Kothrud Depot, Kothrud, Pune', '411038', '+91 20 4000 1102', 'tvs.pune.kothrud@dealer-demo.in', 'https://maps.google.com/?q=TVS+Motor+Authorised+Dealer+Kothrud', 4.6, '["Aditya Joshi (Sales Consultant)", "Priya Deshmukh (Product Specialist)"]'),
('tvs_bengaluru_indiranagar', 'tvs', 'TVS Motor Authorised Dealer – Indiranagar', 'Bengaluru', 'Karnataka', 'Indiranagar', 'No. 312, 100 Feet Road, HAL 2nd Stage, Indiranagar, Bengaluru', '560038', '+91 80 4000 1103', 'tvs.bengaluru.indiranagar@dealer-demo.in', 'https://maps.google.com/?q=TVS+Motor+Authorised+Dealer+Indiranagar', 4.8, '["Karthik Reddy (Performance Bikes Specialist)", "Ananya Rao (EV Specialist)"]'),
('tvs_delhi_karol_bagh', 'tvs', 'TVS Motor Authorised Dealer – Karol Bagh', 'Delhi', 'Delhi', 'Karol Bagh', '12/8, Pusa Road, Near Karol Bagh Metro Station, New Delhi', '110005', '+91 11 4000 1104', 'tvs.delhi.karol.bagh@dealer-demo.in', 'https://maps.google.com/?q=TVS+Motor+Authorised+Dealer+Karol+Bagh', 4.6, '["Vikram Singh (Sales Consultant)", "Neha Arora (Finance Advisor)"]'),
('tvs_chennai_anna_nagar', 'tvs', 'TVS Motor Authorised Dealer – Anna Nagar', 'Chennai', 'Tamil Nadu', 'Anna Nagar', 'AE-45, 2nd Avenue, Anna Nagar, Chennai', '600040', '+91 44 4000 1105', 'tvs.chennai.anna.nagar@dealer-demo.in', 'https://maps.google.com/?q=TVS+Motor+Authorised+Dealer+Anna+Nagar', 4.8, '["Arun Kumar (Sales Consultant)", "Divya Subramanian (Product Specialist)"]'),
('tvs_hyderabad_kukatpally', 'tvs', 'TVS Motor Authorised Dealer – Kukatpally', 'Hyderabad', 'Telangana', 'Kukatpally', 'Plot 7, JNTU–Hitech City Road, KPHB Colony, Kukatpally, Hyderabad', '500072', '+91 40 4000 1106', 'tvs.hyderabad.kukatpally@dealer-demo.in', 'https://maps.google.com/?q=TVS+Motor+Authorised+Dealer+Kukatpally', 4.7, '["Srinivas Rao (Sales Consultant)", "Lakshmi Prasanna (EV Specialist)"]'),
('hero_mumbai_ghatkopar', 'hero_motocorp', 'Hero MotoCorp Authorised Dealer – Ghatkopar East', 'Mumbai', 'Maharashtra', 'Ghatkopar East', 'Unit 3, R.B. Mehta Marg, Near Ghatkopar Station, Ghatkopar East, Mumbai', '400077', '+91 22 4000 2201', 'hero.mumbai.ghatkopar@dealer-demo.in', 'https://maps.google.com/?q=Hero+MotoCorp+Authorised+Dealer+Ghatkopar+East', 4.6, '["Rohan Patil (Sales Consultant)", "Meera Iyer (Finance Advisor)"]'),
('hero_pune_hadapsar', 'hero_motocorp', 'Hero MotoCorp Authorised Dealer – Hadapsar', 'Pune', 'Maharashtra', 'Hadapsar', 'S. No. 150, Pune–Solapur Road, Near Magarpatta Chowk, Hadapsar, Pune', '411028', '+91 20 4000 2202', 'hero.pune.hadapsar@dealer-demo.in', 'https://maps.google.com/?q=Hero+MotoCorp+Authorised+Dealer+Hadapsar', 4.7, '["Saurabh Pawar (Sales Consultant)", "Pooja Shinde (Product Specialist)"]'),
('hero_bengaluru_koramangala', 'hero_motocorp', 'Hero MotoCorp Authorised Dealer – Koramangala', 'Bengaluru', 'Karnataka', 'Koramangala', 'No. 88, 80 Feet Road, 4th Block, Koramangala, Bengaluru', '560034', '+91 80 4000 2203', 'hero.bengaluru.koramangala@dealer-demo.in', 'https://maps.google.com/?q=Hero+MotoCorp+Authorised+Dealer+Koramangala', 4.8, '["Rahul Nair (Sales Consultant)", "Kavitha Gowda (Premium Motorcycles Specialist)"]'),
('hero_delhi_lajpat_nagar', 'hero_motocorp', 'Hero MotoCorp Authorised Dealer – Lajpat Nagar', 'Delhi', 'Delhi', 'Lajpat Nagar', 'A-14, Ring Road, Lajpat Nagar IV, New Delhi', '110024', '+91 11 4000 2204', 'hero.delhi.lajpat.nagar@dealer-demo.in', 'https://maps.google.com/?q=Hero+MotoCorp+Authorised+Dealer+Lajpat+Nagar', 4.6, '["Amit Sharma (Sales Consultant)", "Ritu Malhotra (Finance Advisor)"]'),
('hero_chennai_velachery', 'hero_motocorp', 'Hero MotoCorp Authorised Dealer – Velachery', 'Chennai', 'Tamil Nadu', 'Velachery', 'No. 54, Velachery Main Road, Near Vijayanagar Bus Stand, Velachery, Chennai', '600042', '+91 44 4000 2205', 'hero.chennai.velachery@dealer-demo.in', 'https://maps.google.com/?q=Hero+MotoCorp+Authorised+Dealer+Velachery', 4.7, '["Senthil Murugan (Sales Consultant)", "Keerthana Selvam (Product Specialist)"]'),
('hero_hyderabad_madhapur', 'hero_motocorp', 'Hero MotoCorp Authorised Dealer – Madhapur', 'Hyderabad', 'Telangana', 'Madhapur', 'Plot 19, Ayyappa Society Main Road, Madhapur, Hyderabad', '500081', '+91 40 4000 2206', 'hero.hyderabad.madhapur@dealer-demo.in', 'https://maps.google.com/?q=Hero+MotoCorp+Authorised+Dealer+Madhapur', 4.7, '["Naveen Goud (Sales Consultant)", "Swathi Reddy (EV Specialist)"]');
