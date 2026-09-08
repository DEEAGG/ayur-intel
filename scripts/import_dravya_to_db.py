import sqlite3
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Ensure UTF-8 stdout on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def create_database():
    """Create SQLite database with all tables"""
    
    db_path = Path(__file__).parent.parent / "data" / "dravya.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing database if exists (for clean import)
    if db_path.exists():
        print(f"🗑️ Removing existing database: {db_path}")
        db_path.unlink()
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Create plants table
    cursor.execute('''
        CREATE TABLE plants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER UNIQUE NOT NULL,
            scientific_name TEXT,
            family TEXT,
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create vernacular_names table
    cursor.execute('''
        CREATE TABLE vernacular_names (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            language TEXT NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (plant_id) REFERENCES plants(plant_id) ON DELETE CASCADE
        )
    ''')
    
    # Create plant_properties table
    cursor.execute('''
        CREATE TABLE plant_properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            property_type TEXT NOT NULL,
            property_name TEXT,
            property_value TEXT,
            FOREIGN KEY (plant_id) REFERENCES plants(plant_id) ON DELETE CASCADE
        )
    ''')
    
    # Create etymologies table
    cursor.execute('''
        CREATE TABLE etymologies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            sanskrit_synonym TEXT,
            sanskrit_diacritical TEXT,
            reference TEXT,
            etymology_sanskrit TEXT,
            english_meaning TEXT,
            FOREIGN KEY (plant_id) REFERENCES plants(plant_id) ON DELETE CASCADE
        )
    ''')
    
    # Create mahakashaya table
    cursor.execute('''
        CREATE TABLE mahakashaya (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            name TEXT,
            FOREIGN KEY (plant_id) REFERENCES plants(plant_id) ON DELETE CASCADE
        )
    ''')
    
    # Create varga table
    cursor.execute('''
        CREATE TABLE varga (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            name TEXT,
            FOREIGN KEY (plant_id) REFERENCES plants(plant_id) ON DELETE CASCADE
        )
    ''')
    
    # Create skandha table
    cursor.execute('''
        CREATE TABLE skandha (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            name TEXT,
            FOREIGN KEY (plant_id) REFERENCES plants(plant_id) ON DELETE CASCADE
        )
    ''')
    
    # Create parts_used table
    cursor.execute('''
        CREATE TABLE parts_used (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            part_name TEXT,
            part_hindi TEXT,
            part_diacritical TEXT,
            reference TEXT,
            FOREIGN KEY (plant_id) REFERENCES plants(plant_id) ON DELETE CASCADE
        )
    ''')
    
    # Create indexes for fast search
    print("🔍 Creating indexes...")
    
    cursor.execute('CREATE INDEX idx_plant_plant_id ON plants(plant_id)')
    cursor.execute('CREATE INDEX idx_plant_scientific_name ON plants(scientific_name)')
    cursor.execute('CREATE INDEX idx_vernacular_name ON vernacular_names(name)')
    cursor.execute('CREATE INDEX idx_vernacular_plant_id ON vernacular_names(plant_id)')
    cursor.execute('CREATE INDEX idx_property_type ON plant_properties(property_type)')
    cursor.execute('CREATE INDEX idx_property_plant_id ON plant_properties(plant_id)')
    cursor.execute('CREATE INDEX idx_property_value ON plant_properties(property_value)')
    cursor.execute('CREATE INDEX idx_etymology_plant_id ON etymologies(plant_id)')
    cursor.execute('CREATE INDEX idx_parts_plant_id ON parts_used(plant_id)')
    cursor.execute('CREATE INDEX idx_mahakashaya_plant_id ON mahakashaya(plant_id)')
    
    conn.commit()
    return conn, cursor

def import_data():
    """Import all data from JSON file"""
    
    print("📊 Starting DRAVYA data import...")
    
    # Read JSON file
    json_path = Path(__file__).parent.parent / "dravya_full_data.json"
    
    if not json_path.exists():
        print(f"❌ JSON file not found: {json_path}")
        print("   Please run scrape_dravya.py first")
        return
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    conn, cursor = create_database()
    
    plants = data.get('plants', [])
    total = len(plants)
    print(f"📊 Found {total} plants in JSON file")
    
    imported_count = 0
    
    for idx, plant in enumerate(plants, 1):
        plant_id = plant.get('plant_id')
        scientific_name = plant.get('scientific_name', '').strip()
        family = plant.get('family', '').strip()
        url = plant.get('url', '').strip()
        
        if not plant_id:
            continue
        
        # Insert plant
        cursor.execute('''
            INSERT INTO plants (plant_id, scientific_name, family, url)
            VALUES (?, ?, ?, ?)
        ''', (plant_id, scientific_name, family, url))
        
        # Insert vernacular names
        vernacular = plant.get('vernacular_names', {})
        for language, names in vernacular.items():
            if isinstance(names, list):
                for name in names:
                    if name and str(name).strip():
                        cursor.execute('''
                            INSERT INTO vernacular_names (plant_id, language, name)
                            VALUES (?, ?, ?)
                        ''', (plant_id, language, str(name).strip()))
            elif isinstance(names, str) and names.strip():
                cursor.execute('''
                    INSERT INTO vernacular_names (plant_id, language, name)
                    VALUES (?, ?, ?)
                ''', (plant_id, language, names.strip()))
        
        # Insert properties (Guna, Virya, Vipaka, Karma, Doshakarma, Therapeutic Usage)
        property_mappings = {
            'guna': 'guna',
            'virya': 'virya',
            'vipaka': 'vipaka',
            'karma': 'karma',
            'doshakarma': 'doshakarma',
            'therapeutic_usage': 'therapeutic_usage'
        }
        
        for json_key, prop_type in property_mappings.items():
            value = plant.get(json_key)
            if value:
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            val_name = item.get('name') or item.get('title') or ''
                            if val_name and str(val_name).strip():
                                cursor.execute('''
                                    INSERT INTO plant_properties (plant_id, property_type, property_name, property_value)
                                    VALUES (?, ?, ?, ?)
                                ''', (plant_id, prop_type, 'name', str(val_name).strip()))
                            for k, v in item.items():
                                if k not in ['name', 'title', 'title_ref_book', 'reference_remarks'] and v and str(v).strip():
                                    cursor.execute('''
                                        INSERT INTO plant_properties (plant_id, property_type, property_name, property_value)
                                        VALUES (?, ?, ?, ?)
                                    ''', (plant_id, prop_type, k, str(v).strip()))
                        elif item and str(item).strip():
                            cursor.execute('''
                                INSERT INTO plant_properties (plant_id, property_type, property_name, property_value)
                                VALUES (?, ?, ?, ?)
                            ''', (plant_id, prop_type, '', str(item).strip()))
                elif isinstance(value, dict):
                    for key, val in value.items():
                        if val and str(val).strip():
                            cursor.execute('''
                                INSERT INTO plant_properties (plant_id, property_type, property_name, property_value)
                                VALUES (?, ?, ?, ?)
                            ''', (plant_id, prop_type, str(key), str(val).strip()))
                elif str(value).strip():
                    cursor.execute('''
                        INSERT INTO plant_properties (plant_id, property_type, property_name, property_value)
                        VALUES (?, ?, ?, ?)
                    ''', (plant_id, prop_type, '', str(value).strip()))
        
        # Insert dosage
        dosage = plant.get('dosage') or plant.get('dosage_formulations')
        if dosage:
            if isinstance(dosage, list):
                for item in dosage:
                    if isinstance(item, dict):
                        d_name = item.get('name', '')
                        d_form = item.get('dosageform', '')
                        d_ref = item.get('dosagereference', '')
                        val_str = f"{d_name} ({d_form}) - {d_ref}".strip(" -()") if d_form or d_ref else d_name
                        if val_str:
                            cursor.execute('''
                                INSERT INTO plant_properties (plant_id, property_type, property_name, property_value)
                                VALUES (?, ?, ?, ?)
                            ''', (plant_id, 'dosage', 'formulation' if d_form else 'dose', val_str))
                    elif str(item).strip():
                        cursor.execute('''
                            INSERT INTO plant_properties (plant_id, property_type, property_name, property_value)
                            VALUES (?, ?, ?, ?)
                        ''', (plant_id, 'dosage', '', str(item).strip()))
            elif str(dosage).strip():
                cursor.execute('''
                    INSERT INTO plant_properties (plant_id, property_type, property_name, property_value)
                    VALUES (?, ?, ?, ?)
                ''', (plant_id, 'dosage', '', str(dosage).strip()))
        
        # Insert classical_reference & pharmacopoeial_status
        classical_ref = plant.get('classical_references') or plant.get('classical_reference')
        if classical_ref:
            if isinstance(classical_ref, list):
                for item in classical_ref:
                    if isinstance(item, dict):
                        c_name = item.get('name', '')
                        if c_name:
                            cursor.execute('''
                                INSERT INTO plant_properties (plant_id, property_type, property_name, property_value)
                                VALUES (?, ?, ?, ?)
                            ''', (plant_id, 'classical_reference', '', str(c_name).strip()))
                    elif str(item).strip():
                        cursor.execute('''
                            INSERT INTO plant_properties (plant_id, property_type, property_name, property_value)
                            VALUES (?, ?, ?, ?)
                        ''', (plant_id, 'classical_reference', '', str(item).strip()))
            elif str(classical_ref).strip():
                cursor.execute('''
                    INSERT INTO plant_properties (plant_id, property_type, property_name, property_value)
                    VALUES (?, ?, ?, ?)
                ''', (plant_id, 'classical_reference', '', str(classical_ref).strip()))
        
        # Insert etymology
        etymology_list = plant.get('etymology', [])
        if isinstance(etymology_list, list):
            for item in etymology_list:
                if isinstance(item, dict):
                    cursor.execute('''
                        INSERT INTO etymologies 
                        (plant_id, sanskrit_synonym, sanskrit_diacritical, reference, etymology_sanskrit, english_meaning)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        plant_id,
                        item.get('sanskrit_synonym', ''),
                        item.get('sanskrit_diacritical', ''),
                        item.get('reference', ''),
                        item.get('etymology_sanskrit', ''),
                        item.get('english_meaning', '')
                    ))
        
        # Insert mahakashaya
        mahakashaya_list = plant.get('mahakashaya', [])
        if isinstance(mahakashaya_list, list):
            for item in mahakashaya_list:
                if isinstance(item, dict):
                    name = item.get('name', '')
                    if name and name.strip():
                        cursor.execute('''
                            INSERT INTO mahakashaya (plant_id, name)
                            VALUES (?, ?)
                        ''', (plant_id, name.strip()))
        
        # Insert varga
        varga_list = plant.get('varga', [])
        if isinstance(varga_list, list):
            for item in varga_list:
                if isinstance(item, dict):
                    name = item.get('name', '')
                    if name and name.strip():
                        cursor.execute('''
                            INSERT INTO varga (plant_id, name)
                            VALUES (?, ?)
                        ''', (plant_id, name.strip()))
        
        # Insert skandha
        skandha_list = plant.get('skandha', [])
        if isinstance(skandha_list, list):
            for item in skandha_list:
                if isinstance(item, dict):
                    name = item.get('name', '')
                    if name and name.strip():
                        cursor.execute('''
                            INSERT INTO skandha (plant_id, name)
                            VALUES (?, ?)
                        ''', (plant_id, name.strip()))
        
        # Insert parts_used
        parts_list = plant.get('parts_used', [])
        if isinstance(parts_list, list):
            for item in parts_list:
                if isinstance(item, dict):
                    # extract part name, hindi, diacritical, reference
                    p_name = item.get('name') or item.get('part_name') or ''
                    p_hindi = item.get('part_hindi') or item.get('उपयग_हससहनद') or ''
                    p_diacritical = item.get('part_diacritical') or item.get('part_useddiacritical') or ''
                    p_ref = item.get('reference') or item.get('title_ref_book') or ''
                    cursor.execute('''
                        INSERT INTO parts_used (plant_id, part_name, part_hindi, part_diacritical, reference)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        plant_id,
                        p_name,
                        p_hindi,
                        p_diacritical,
                        p_ref
                    ))
        
        # Progress tracking
        if idx % 50 == 0:
            print(f"   ✅ Imported {idx}/{total} plants")
        
        imported_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Successfully imported {imported_count} plants into data/dravya.db")
    print(f"   📍 Database location: {Path(__file__).parent.parent / 'data' / 'dravya.db'}")

def verify_import():
    """Verify the import was successful"""
    
    db_path = Path(__file__).parent.parent / "data" / "dravya.db"
    
    if not db_path.exists():
        print("❌ Database not found!")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get counts
    cursor.execute("SELECT COUNT(*) FROM plants")
    plant_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM vernacular_names")
    vernacular_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM plant_properties")
    property_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM etymologies")
    etymology_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM parts_used")
    parts_count = cursor.fetchone()[0]
    
    # Get sample plant
    cursor.execute("SELECT plant_id, scientific_name, family FROM plants LIMIT 5")
    sample_plants = cursor.fetchall()
    
    conn.close()
    
    print("\n📊 Verification Results:")
    print(f"   🌿 Total Plants: {plant_count}")
    print(f"   🌐 Vernacular Names: {vernacular_count}")
    print(f"   📋 Properties: {property_count}")
    print(f"   📚 Etymologies: {etymology_count}")
    print(f"   🪴 Parts Used: {parts_count}")
    print("\n   📌 Sample Plants:")
    for plant_id, name, family in sample_plants:
        print(f"      • ID {plant_id}: {name} ({family})")

if __name__ == "__main__":
    print("=" * 60)
    print("🌿 DRAVYA DATA IMPORT")
    print("=" * 60)
    import_data()
    verify_import()
    print("\n✅ Import complete!")
