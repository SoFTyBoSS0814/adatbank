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

    def extract_teams_from_row(self, row, found_time):
        """Cellánként vizsgálja a sort, és kiszűri a státuszt, időpontot, dátumot és fordulót."""
        tds = row.find_all('td')
        if not tds:
            # Ha nincsenek <td> elemek, fallback a sima szövegre, de kiszűrve a jegyzőkönyvet
            row_text = row.get_text(separator=' - ', strip=True)
            if "jegyzőkönyv" in row_text.lower():
                row_text = row_text.lower().split("jegyzőkönyv")[0]
            return row_text

        valid_texts = []
        for td in tds:
            td_text = td.get_text(separator=' ', strip=True)
            
            # Kihagyjuk az üres, státusz, dátum, időpont vagy fordulószám cellákat
            if not td_text:
                continue
            if 'jegyzőkönyv' in td_text.lower() or 'részleges' in td_text.lower() or 'státusz' in td_text.lower():
                continue
            if re.search(r'\d{4}\.\d{2}\.\d{2}', td_text) or found_time in td_text:
                continue
            # Kihagyjuk a meccs közbeni dobozokat (pl. piros - mező) vagy kis számokat (forduló)
            if td_text in ['-', '--', 'v', 'h', 'gy'] or (td_text.isdigit() and len(td_text) <= 2):
                continue
                
            valid_texts.append(td_text)

        # Összeillesztjük a megmaradt cellákat (csapatnevek)
        cleaned = " - ".join(valid_texts)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        cleaned = re.sub(r'^[\-\|\s]+|[\-\|\s]+$', '', cleaned)
        return cleaned

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
                rows = soup.find_all(['tr', 'div'], class_=re.compile('match|row|item|sorsolas|elem', re.I))
                if not rows:
                    rows = soup.find_all('tr')

                for row in rows:
                    row_text = row.get_text(separator=' ', strip=True)
                    
                    time_match = time_pattern.search(row_text)
                    if not time_match:
                        continue
                    
                    found_time = time_match.group(1)

                    if self.is_time_in_range(found_time):
                        # Kinyerjük kizárólag a csapatokat a cellákból
                        team_names = self.extract_teams_from_row(row, found_time)
                        
                        if len(team_names) > 3:
                            match_data = {
                                "szervezet": szervezet_id,
                                "statusz": "jovobeni",
                                "datum": self.target_date,
                                "idopont": found_time,
                                "nyers_szöveg": team_names[:120]
                            }
                            
                            if match_data not in all_filtered_matches:
                                all_filtered_matches.append(match_data)

            except requests.exceptions.RequestException as e:
                print(f"Hálózati hiba a szervezet={szervezet_id}-nél: {e}")

            time_module.sleep(0.2)

        # Időrendi sorrendbe rendezés: legkorábbitól a legkésőbbig
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
