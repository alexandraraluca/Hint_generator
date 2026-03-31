"""
Script pentru a merge toate fisierele JSON din code_solution_hints_folder
intr-un singur fisier JSON.
"""

import json
import os
import glob
from pathlib import Path


def merge_json_files(source_folder="../code_solution_hints_folder", 
                     output_file="code_solution_hints_tutorial_saved.json"):
    """
    Citeste toate fisierele JSON din source_folder si le combina intr-un singur dictionar.
    Salveaza rezultatul in output_file.
    
    Args:
        source_folder: Folderul cu fisierele JSON de source
        output_file: Fisierul JSON de output
    """
    
    # Verificam daca folderul exista
    if not os.path.exists(source_folder):
        print(f"❌ Error: Folder '{source_folder}' not found!")
        return False
    
    merged_data = {}
    total_files = 0
    total_problems = 0
    
    print(f"\n{'='*60}")
    print(f"Merging JSON files from '{source_folder}'")
    print(f"{'='*60}\n")
    
    # Gasim toate fisierele .json din folderul source
    json_files = sorted(glob.glob(os.path.join(source_folder, "*.json")))
    
    if not json_files:
        print(f"❌ No JSON files found in '{source_folder}'")
        return False
    
    print(f"Found {len(json_files)} JSON files:\n")
    
    # Citim fiecare fisier JSON
    for json_file in json_files:
        filename = os.path.basename(json_file)
        print(f"  📄 Processing: {filename}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                # Adaugam datele din acest fisier la merged_data
                # Verificam pentru conflicte de chei
                conflicts = set(merged_data.keys()) & set(data.keys())
                if conflicts:
                    print(f"      ⚠️  Found {len(conflicts)} duplicate keys: {list(conflicts)[:5]}...")
                
                # Merge: datele din fisierul curent vor suprascrie datele existente (daca exista)
                merged_data.update(data)
                count = len(data)
                total_problems += count
                print(f"      ✓ Added/Updated {count} entries")
            
            total_files += 1
            
        except json.JSONDecodeError as e:
            print(f"      ❌ Error reading JSON: {str(e)}")
        except Exception as e:
            print(f"      ❌ Error processing file: {str(e)}")
    
    print(f"\n{'='*60}")
    print(f"Merge Summary:")
    print(f"  Total files processed: {total_files}")
    print(f"  Total unique problems: {len(merged_data)}")
    print(f"  Total entries: {total_problems}")
    print(f"{'='*60}\n")
    
    # Salvam rezultatul in fisierul output
    print(f"💾 Saving merged data to '{output_file}'...")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
        
        file_size = os.path.getsize(output_file) / (1024 * 1024)  # in MB
        print(f"✅ Successfully saved! File size: {file_size:.2f} MB")
        print(f"✅ Output file: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving output file: {str(e)}")
        return False


if __name__ == "__main__":
    # Merge files
    success = merge_json_files(
        source_folder="../code_solution_hints_folder",
        output_file="code_solution_hints_tutorial_saved.json"
    )
    
    if success:
        print("\n✅ Done! All JSON files have been merged successfully!")
    else:
        print("\n❌ Merge failed. Please check the errors above.")
