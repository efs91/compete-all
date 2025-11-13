# Exemples de Configurations de Places

Ce dossier contient des exemples de configurations JSON pour les plages de places dans le système de scoring.

## Fichiers disponibles

### 1. `podium-classique.json`
Configuration simple pour un podium traditionnel :
- 1ère place : 25 points
- 2ème place : 18 points  
- 3ème place : 15 points

**Cas d'usage :** Petites compétitions avec récompenses pour le top 3 uniquement.

### 2. `top10-standard.json`
Configuration détaillée pour les 10 premières places :
- Places 1-10 : points décroissants (25, 18, 15, 12, 10, 8, 6, 4, 2, 1)
- Place 11+ : 0 points

**Cas d'usage :** Compétitions moyennes où vous voulez récompenser le top 10.

### 3. `marathon-longue-distance.json`
Configuration par plages pour grandes compétitions :
- 1ère : 100 pts
- 2ème : 80 pts
- 3ème : 60 pts
- 4-5 : 50 pts
- 6-10 : 40 pts
- 11-15 : 30 pts
- 16-20 : 20 pts
- 21+ : 10 pts

**Cas d'usage :** Courses avec beaucoup de participants (marathon, trail, etc.).

### 4. `groupes-simples.json`
Configuration par groupes simples :
- Places 1-3 : 3 points
- Places 4-6 : 2 points
- Places 7-10 : 1 point
- Place 11+ : 0 points

**Cas d'usage :** Compétitions amicales où l'important est de participer.

## Comment utiliser

### Dans l'interface web :
1. Allez dans la section "Scoring par Classement"
2. Cliquez sur "📤 Importer JSON"
3. Sélectionnez un des fichiers d'exemple
4. Les plages seront automatiquement chargées dans le formulaire

### Via templates prédéfinis :
Utilisez le menu déroulant "Templates" pour charger rapidement :
- 🥇 Podium (3 places)
- 🏆 Top 10
- 🏃 Course longue (20 places)

### Créer votre propre configuration :
1. Configurez vos plages dans l'interface
2. Cliquez sur "📥 Exporter JSON"
3. Le fichier sera téléchargé avec un timestamp
4. Vous pouvez le réutiliser ou le partager

## Format JSON

```json
{
  "placeRanges": [
    {
      "from": 1,
      "to": 3,
      "points": 10
    }
  ],
  "lastPlaceZero": true,
  "exportedAt": "2025-11-12T00:00:00.000Z",
  "version": "1.0",
  "description": "Description optionnelle"
}
```

### Champs requis :
- `placeRanges` : Array de plages avec `from`, `to`, `points`
- `lastPlaceZero` : Boolean - dernière place à 0 points ?

### Champs optionnels :
- `exportedAt` : Date d'export
- `version` : Version du format
- `description` : Description de la configuration

## Validation

Le système valide automatiquement :
- ✅ `from` doit être ≤ `to`
- ✅ Pas de chevauchement entre plages
- ✅ Tri automatique par ordre croissant
- ✅ Format JSON valide
