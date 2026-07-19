-- ============================================================================
-- 002_seed_stock_instruments.sql
--
-- Einmaliger Seed fuer trading.stock_instruments. Name/Sektor stammen aus
-- der bereits produktiv befuellten n8n Data Table stock_technical_signals
-- (von Workflow 02 taeglich geschrieben), Aliase/Ausschlussmuster aus dem
-- bestehenden RSS-Vorfilter in "03 – News Ingestion stündlich.json"
-- (Node "RSS-Feeds laden & filtern") -- nichts davon erfunden, alles aus
-- bereits vorhandenem, verifiziertem Code/Daten uebernommen.
--
-- Wiederholbar: ON CONFLICT (ticker) DO UPDATE, kann gefahrlos erneut
-- ausgefuehrt werden (z.B. nach Aenderungen an Aliasen).
-- ============================================================================

INSERT INTO trading.stock_instruments
  (ticker, name, sektor, aktiv, sortierung, aliases_json, exclude_patterns_json, benchmark_symbol)
VALUES
  ('SAP.DE',  'SAP SE',             'Technologie',  TRUE, 1,  '["SAP","SAP SE"]'::jsonb,
    '["WhatsApp"]'::jsonb, '^GDAXI'),
  ('SIE.DE',  'Siemens AG',         'Industrie',    TRUE, 2,  '["Siemens","Siemens AG"]'::jsonb,
    '[]'::jsonb, '^GDAXI'),
  ('BASF.DE', 'BASF SE',            'Chemie',       TRUE, 3,  '["BASF","BASF SE"]'::jsonb,
    '[]'::jsonb, '^GDAXI'),
  ('ALV.DE',  'Allianz SE',         'Versicherung', TRUE, 4,  '["Allianz","Allianz SE"]'::jsonb,
    '["Allianzen","Allianzpartner"]'::jsonb, '^GDAXI'),
  ('MBG.DE',  'Mercedes-Benz',      'Auto',         TRUE, 5,  '["Mercedes","Mercedes-Benz","Mercedes Benz","Daimler"]'::jsonb,
    '[]'::jsonb, '^GDAXI'),
  ('BMW.DE',  'BMW AG',             'Auto',         TRUE, 6,  '["BMW","BMW AG"]'::jsonb,
    '[]'::jsonb, '^GDAXI'),
  ('VOW3.DE', 'Volkswagen VZ',      'Auto',         TRUE, 7,  '["Volkswagen","Volkswagen AG","VW"]'::jsonb,
    '["VW Käfer","VW-Bus Oldtimer"]'::jsonb, '^GDAXI'),
  ('DBK.DE',  'Deutsche Bank',      'Banken',       TRUE, 8,  '["Deutsche Bank","Deutsche Bank AG"]'::jsonb,
    '[]'::jsonb, '^GDAXI'),
  ('DTE.DE',  'Deutsche Telekom',   'Telekom',      TRUE, 9,  '["Deutsche Telekom","Telekom","T-Mobile"]'::jsonb,
    '[]'::jsonb, '^GDAXI'),
  ('RWE.DE',  'RWE AG',             'Energie',      TRUE, 10, '["RWE AG","RWE"]'::jsonb,
    '["Rot-Weiss Essen","Rot Weiss Essen","Rot-Weiß Essen","RWE Essen","RWE-Abwehrchef","RWE-Fans","RWE-Spieler","RWE-Trainer","RWE-Profi","RWE-Keeper","Relegation","Fußball"]'::jsonb, '^GDAXI'),
  ('BAYN.DE', 'Bayer AG',           'Pharma',       TRUE, 11, '["Bayer AG","Bayer"]'::jsonb,
    '["Bayern","Niederbayern","Oberbayern","Bayerischer","Bayerische","Bayerisches","FC Bayern"]'::jsonb, '^GDAXI'),
  ('EOAN.DE', 'E.ON SE',            'Energie',      TRUE, 12, '["E.ON SE","E.ON","EON"]'::jsonb,
    '[]'::jsonb, '^GDAXI'),
  ('ADS.DE',  'adidas AG',          'Sport',        TRUE, 13, '["adidas AG","adidas"]'::jsonb,
    '[]'::jsonb, '^GDAXI'),
  ('HEN3.DE', 'Henkel VZ',          'Konsumgüter',  TRUE, 14, '["Henkel AG","Henkel"]'::jsonb,
    '[]'::jsonb, '^GDAXI'),
  ('FRE.DE',  'Fresenius SE',       'Gesundheit',   TRUE, 15, '["Fresenius SE","Fresenius"]'::jsonb,
    '[]'::jsonb, '^GDAXI')
ON CONFLICT (ticker) DO UPDATE SET
  name = EXCLUDED.name,
  sektor = EXCLUDED.sektor,
  aliases_json = EXCLUDED.aliases_json,
  exclude_patterns_json = EXCLUDED.exclude_patterns_json,
  benchmark_symbol = EXCLUDED.benchmark_symbol,
  updated_at = now();
