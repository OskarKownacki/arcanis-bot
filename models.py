from dataclasses import dataclass, field
from typing import List

@dataclass
class Player:
    # Podstawowe typy danych
    id: int               # ID użytkownika z Discorda (interaction.user.id)
    nickname: str             # Nick z Discorda
    rankingPoints: int = 0     # Punkty rankingowe, domyślnie 0
    rankingPosition: int = 0   # Pozycja w rankingu, domyślnie 0
    online: bool = False         # Czy gracz jest online, domyślnie False
    def print_info(self):
        print(f"ID: {self.id}, Nickname: {self.nickname}, Ranking Points: {self.rankingPoints}, Ranking Position: {self.rankingPosition}, Online: {self.online}")