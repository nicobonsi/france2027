# France 2027

La France — métropole **et outre-mer** — en données publiques, département par département, avec une ambition :
permettre, avant la présidentielle de 2027, de confronter les programmes des candidats à la situation réelle du pays.

Inspiré par [usaciv](https://karpathy.ai/usaciv/) (les États-Unis dessinés comme une carte de jeu de stratégie),
mais avec une différence de fond : usaciv décrit, France 2027 veut aussi **simuler**.

## Ce qui existe (v0.1 — la carte)

- Carte SVG des 101 départements : métropole en Lambert-93, chaque DROM dans son encart et sa projection,
  un encart agrandi pour Paris et la petite couronne.
- Les collectivités d'outre-mer (Nouvelle-Calédonie, Polynésie, Wallis-et-Futuna, Saint-Pierre-et-Miquelon,
  Saint-Martin/Saint-Barthélemy) et les Français de l'étranger, sous forme de tuiles : l'IGN ne publie pas leurs contours
  dans ADMIN EXPRESS, et on n'invente pas de géographie.
- 24 indicateurs (« lentilles ») : population, densité, croissance, solde naturel, niveau de vie médian, pauvreté,
  chômage et son évolution, tissu d'établissements, logement, résultats des deux tours de la présidentielle 2022.
- Fiche par territoire (valeurs, rang, moyenne nationale, résultats 2022), recherche, lien partageable
  (`#indicateur=…&territoire=…`), Almanach qui documente chaque chiffre et sa source.
- En ligne : https://nicobonsi.github.io/france2027/ (mis à jour automatiquement à chaque push sur `main`).
- **Règle d’or : rien n'est estimé.** Quand une source ne couvre pas un territoire, il est hachuré « non publié ».

### Les trous de données, à connaître

| Source | Ce qui manque |
|---|---|
| Recensement (Insee, millésime 2023) | Mayotte (calendrier de recensement distinct, absent de la base comparateur) |
| Filosofi 2023 (revenus, pauvreté) | Guadeloupe, Martinique, Guyane, Mayotte — seule La Réunion est couverte parmi les DROM |
| Chômage localisé (Insee) | Mayotte (enquête Emploi annuelle distincte). Séries DROM très volatiles d'un trimestre à l'autre |
| Toutes les sources Insee | Les COM : elles ont leurs propres instituts (ISEE, ISPF…) et souvent leur propre fiscalité |
| Résultats électoraux | Rien : couvrent tous les territoires, y compris l'étranger |

## Structure

```
pipeline/            Python : téléchargement des sources brutes → JSON prêts pour le site
  sources.py         liste de toutes les sources (URL, éditeur, licence)
  fetch.py           télécharge dans pipeline/raw/ (non versionné)
  build.py           projette, simplifie, calcule les indicateurs → web/data/*.json
web/                 site statique, sans framework ni étape de build
  data/              sorties du pipeline (versionnées : le site fonctionne tel quel)
  js/  css/
```

## Lancer

```bash
pip install -r pipeline/requirements.txt
python pipeline/fetch.py      # ~40 Mo de sources brutes
python pipeline/build.py      # régénère web/data/
python -m http.server -d web 8000   # puis http://localhost:8000
```

## Feuille de route

1. **Carte** (fait, à enrichir) : chômage des jeunes, âge, diplômes, santé, finances locales, législatives 2024,
   niveau commune/circonscription pour la métropole.
2. **Bac à sable budgétaire** : modélisation statique des prélèvements et prestations avec
   [OpenFisca-France](https://github.com/openfisca/openfisca-france) — coût d'une mesure, gagnants et perdants
   par décile, type de ménage et territoire. Haute confiance sur l'arithmétique, et seulement là.
3. **Programmes** : extraction mesure par mesure des programmes (d'abord ceux des législatives 2024 pour éprouver
   la méthode, puis ceux de 2027), chaque mesure classée *statique / dépense / comportementale / non chiffrable*,
   avec taux de couverture par programme, chiffrage du candidat vs le nôtre, et droit de réponse.
4. Les effets comportementaux et macro ne seront présentés que sous forme de **fourchettes** avec hypothèses nommées.

## Licence des données

Toutes les sources sont publiées sous Licence Ouverte Etalab 2.0 (IGN, Insee, ministère de l'Intérieur) ;
voir `pipeline/sources.py` et l'Almanach du site.
