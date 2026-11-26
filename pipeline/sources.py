"""Every raw file the pipeline uses, with where it comes from.

`id` is what web/data/sources.json and each lens refer to; `files` are downloaded into pipeline/raw/.
Update a URL here when INSEE or the Ministry publishes a new vintage, then rerun fetch.py and build.py.
"""

WFS = "https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&OUTPUTFORMAT=application/json&SRSNAME=EPSG:4326&TYPENAMES="

SOURCES = [
    {
        "id": "ign_admin_express",
        "title": "ADMIN EXPRESS COG CARTO (départements, régions, chefs-lieux)",
        "publisher": "IGN — Géoplateforme",
        "page": "https://geoservices.ign.fr/adminexpress",
        "licence": "Licence Ouverte Etalab 2.0",
        "files": {
            "dep.geojson": WFS + "ADMINEXPRESS-COG-CARTO.LATEST:departement",
            "reg.geojson": WFS + "ADMINEXPRESS-COG-CARTO.LATEST:region",
            "chefs_dep.geojson": WFS + "ADMINEXPRESS-COG-CARTO.LATEST:chef_lieu_de_departement",
        },
    },
    {
        "id": "insee_comparateur",
        "title": "Base du comparateur de territoires (recensement 2023, Filosofi 2023, état civil, Flores)",
        "publisher": "Insee",
        "page": "https://www.insee.fr/fr/statistiques/2521169",
        "licence": "Licence Ouverte Etalab 2.0",
        "files": {"comparateur_csv.zip": "https://www.insee.fr/fr/statistiques/fichier/2521169/comparateur_csv.zip"},
    },
    {
        "id": "insee_chomage",
        "title": "Taux de chômage localisés par département (moyenne trimestrielle, CVS)",
        "publisher": "Insee",
        "page": "https://www.insee.fr/fr/statistiques/2012804",
        "licence": "Licence Ouverte Etalab 2.0",
        "files": {"sl_etc.xls": "https://www.insee.fr/fr/statistiques/fichier/2012804/sl_etc_2026T2.xls"},
    },
    {
        "id": "mi_pres2022_t1",
        "title": "Élection présidentielle 2022 — résultats définitifs du 1er tour par département",
        "publisher": "Ministère de l'Intérieur",
        "page": "https://www.data.gouv.fr/fr/datasets/62581fdf02e05e365ea227a1/",
        "licence": "Licence Ouverte Etalab 2.0",
        "files": {
            "pres2022_t1_dpt.xlsx": "https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-1er-tour/20220414-152411/resultats-par-niveau-dpt-t1-france-entiere.xlsx"
        },
    },
    {
        "id": "mi_pres2022_t2",
        "title": "Élection présidentielle 2022 — résultats définitifs du 2nd tour par département",
        "publisher": "Ministère de l'Intérieur",
        "page": "https://www.data.gouv.fr/fr/datasets/626a86215fb310e32b48b137/",
        "licence": "Licence Ouverte Etalab 2.0",
        "files": {
            "pres2022_t2_dpt.xlsx": "https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-2nd-tour/20220428-142147/resultats-par-niveau-dpt-t2-france-entiere.xlsx"
        },
    },
]
