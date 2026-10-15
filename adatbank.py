import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, time
import time as time_module
import re

class MLSZJovobeniFetcher:
    def __init__(self, target_date="2026-10-16"):
        self.target_date = target_date
        self.base_url = "https://ada1bank.mlsz.hu/merkozesnap"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "hu-HU,hu;q=0.9,en;q=0.8"
        }
        # Kért idősáv: 10:00 - 15:30
        self.start_time = time(10, 0)
        self.end_time = time(15, 30)

    def is_time_in_range(self, time_str):
        """Ellenőrzi, hogy a meccs 10:00 és 15:30 között kezdődik-e."""
        try:
            clean_time_str = time_str.strip()
            match_time = datetime.strptime(clean_time_str, "%H:%M").time()
            return self.start_time <= match_time <= self.end_time
        except ValueError:
            return False

    def fetch_all_organizations(self):
        all_filtered_matches = []
        time_pattern = re.compile(r'\b(\d{2}:\d{2})\b')

        for szervezet_id in range(0, 21):
            params = {
                "statusz": "jovobeni",
                "datum": self.target_date,
                "szervezet": szervezet_id
            }

            try:
                response = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
                
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                rows = soup.find_all(['tr', 'div', 'li'])

                for row in rows:
                    row_text = row.get_text(separator=' ', strip=True)
                    
                    time_match = time_pattern.search(row_text)
                    if not time_match:
                        continue
                    
                    found_time = time_match.group(1)

                    if self.is_time_in_range(found_time):
                        match_data = {
                            "szervezet": szervezet_id,
                            "statusz": "jovobeni",
                            "datum": self.target_date,
                            "idopont": found_time,
                            "nyers_szöveg": row_text[:120]
                        }
                        
                        # Elkerüljük a duplikációkat ugyanazon szervezet/időpont kombinációnál
                        if match_data not in all_filtered_matches:
                            all_filtered_matches.append(match_data)

            except requests.exceptions.RequestException as e:
                print(f"Hálózati hiba a szervezet={szervezet_id}-nél: {e}")

            time_module.sleep(0.2)

        # IDŐRENDI SORRENDBE RENDEZÉS: az 'idopont' mező alapján legkorábbitól legkésőbbig
        all_filtered_matches.sort(key=lambda x: x["idopont"])

        print(f"\n[INFO] Siker! Talált mérkőzések száma időrendbe rendezve: {len(all_filtered_matches)}")
        return all_filtered_matches

    def save_to_json(self, matches, filename="matches.json"):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(matches, f, ensure_ascii=False, indent=4)
        print(f"[OK] Mentve ide: {filename}")

if __name__ == "__main__":
    fetcher = MLSZJovobeniFetcher(target_date="2026-10-16")
    results = fetcher.fetch_all_organizations()
    fetcher.save_to_json(results)
