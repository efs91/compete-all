"""
Génération des brackets de tournoi à élimination directe.
Utilise l'algorithme de test_bracket_algo.py
"""


def generate_bracket_order(n: int) -> list[int]:
    """
    Génère l'ordre des seeds dans un bracket (de haut en bas).
    Algorithme: partir de la finale (1 vs 2) et "ouvrir" le bracket.
    """
    if n < 2 or (n & (n - 1)) != 0:
        raise ValueError("n doit être une puissance de 2")
    
    seeds = [1, 2]
    
    while len(seeds) < n:
        size = len(seeds)
        total = 2 * size + 1
        new_seeds = []
        
        for i in range(0, size, 2):
            top = seeds[i]
            bottom = seeds[i + 1]
            
            new_seeds.append(top)
            new_seeds.append(total - top)
            new_seeds.append(total - bottom)
            new_seeds.append(bottom)
        
        seeds = new_seeds
    
    return seeds


def get_bracket_pairings(bracket_size: int) -> list[tuple[int, int]]:
    """
    Retourne les paires de matchs.
    Exemple pour 8: [(1,8), (4,5), (3,6), (7,2)]
    """
    seeds = generate_bracket_order(bracket_size)
    paires = []
    for i in range(0, len(seeds), 2):
        paires.append((seeds[i], seeds[i + 1]))
    return paires
