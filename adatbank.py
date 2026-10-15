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

    def clean_row_text(self, text, found_time):
        """Kiszűri a sallangokat és egységesíti a csapatnevek közötti elválasztást."""
        # Oldalmenü / fejléc szűrés
        if any(w in text.lower() for w in ["összes", "jelenleg futó", "bács-kiskun", "baranya", "békés"]):
            return ""

        # 1. Levágás a 'jegyzőkönyv'-nél
        if "jegyzőkönyv" in text.lower():
            text = text.lower().split("jegyzőkönyv")[0]
            
        # 2. Levágás az időpontnál
        if found_time in text:
            text = text.split(found_time)[0]

        # 3. Dátumok és felesleges szavak törlése
        text = re.sub(r'\d{4}\.\d{2}\.\d{2}.*', '', text)
        
        unwanted_words = ["mérkőzés", "forduló", "ford\\.", "dátum", "státusz"]
        for word in unwanted_words:
            text = re.sub(word, "", text, flags=re.IGNORECASE)

        # 4. KÖTŐJELEK EGYSÉGESÍTÉSE: Mindenféle többszörös kötőjelet, elválasztót sima " - "-ra cserélünk
        text = re.sub(r'[\s\-\|\–\—]+', ' ', text).strip()
        
        # Ha maradtak kulcsszavak vagy szóköz-problémák, rendezzük
        cleaned = re.sub(r'\s+', ' ', text).strip()
        cleaned = re.sub(r'\s+\d{1,2}$', '', cleaned).strip() # Esetleges fordulószám a végén
        
        # Ha a split/tisztítás után több darabra esett szét, illesszük össze pontosan egy kötőjellel
        parts = [p for p in cleaned.split() if p]
        if len(parts) >= 2:
            # Megpróbáljuk észszerűen kettéválasztani a hazai és vendég csapatot a közepénél
            mid = len(parts) // 2
            hazai = " ".join(parts[:mid])
            vendeg = " ".join(parts[mid:])
            cleaned = f"{hazai} - {vendeg}"
        else:
            cleaned = " ".join(parts)

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
                rows = soup.find_all(['tr', 'div', 'li'])

                for row in rows:
                    row_text = row.get_text(separator=' - ', strip=True)
                    
                    time_match = time_pattern.search(row_text)
                    if not time_match:
                        continue
                    
                    found_time = time_match.group(1)

                    if self.is_time_in_range(found_time):
                        cleaned_txt = self.clean_row_text(row_text, found_time)
                        
                        if len(cleaned_txt) > 3:
                            match_data = {
                                "szervezet": szervezet_id,
                                "statusz": "jovobeni",
                                "datum": self.target_date,
                                "idopont": found_time,
                                "nyers_szöveg": cleaned_txt[:120]
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
