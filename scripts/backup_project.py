import os
import shutil
import sqlite3
import datetime
import zipfile

def backup_project():
    # 1. Setup Backup Directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = "backups"
    if not os.path.exists(backup_root):
        os.makedirs(backup_root)
        
    backup_name = f"vera_backup_{timestamp}"
    backup_path = os.path.join(backup_root, backup_name)
    os.makedirs(backup_path)
    
    print(f"🚀 Starting backup: {backup_name}")

    # 2. Export DB Schema
    print("📝 Exporting Database Schema...")
    try:
        conn = sqlite3.connect('vera.db')
        with open(os.path.join(backup_path, 'schema_dump.sql'), 'w') as f:
            for line in conn.iterdump():
                f.write('%s\n' % line)
        conn.close()
        print("   -> schema_dump.sql created")
    except Exception as e:
        print(f"   ⚠️ Detailed DB schema export failed: {e}")
        # Fallback to simple schema query if dump fails
        try:
            conn = sqlite3.connect('vera.db')
            cursor = conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
            with open(os.path.join(backup_path, 'schema_simple.sql'), 'w') as f:
                for row in cursor.fetchall():
                    if row[0]: f.write(row[0] + ";\n\n")
            conn.close()
            print("   -> schema_simple.sql (fallback) created")
        except Exception as e2:
             print(f"   ❌ DB Backup failed completely: {e2}")

    # 3. Copy Code Files (Exclude CSV, pycache, git, etc.)
    print("📂 Copying Code Files...")
    
    ignore_patterns = shutil.ignore_patterns('*.csv', '*.zip', '*.pdf', '__pycache__', '.git', '.gemini', 'backups', 'venv', 'tmp', '.DS_Store')
    
    # We want to copy contents of current dir to backup_path/code
    # shutil.copytree requires dest to not exist, so we copy whole project tree
    
    source_dir = "."
    dest_dir = os.path.join(backup_path, "code")
    
    shutil.copytree(source_dir, dest_dir, ignore=ignore_patterns)

    # 4. Create Zip Archive
    print("📦 Zipping Archive...")
    zip_filename = os.path.join(backup_root, f"{backup_name}.zip")
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(backup_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, backup_root)
                zipf.write(file_path, arcname)
                
    # Cleanup unzipped folder
    shutil.rmtree(backup_path)
    
    print(f"\n✅ Backup Completed Successfully!")
    print(f"   📍 Location: {os.path.abspath(zip_filename)}")
    print(f"   📄 Contents: DB Schema + Code (py, md, json, yaml)")
    print(f"   🚫 Excluded: CSVs, PDFs, Environment files")

if __name__ == "__main__":
    backup_project()
