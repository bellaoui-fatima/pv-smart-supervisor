"""
Base de connaissances statique pour le diagnostic des centrales photovoltaïques.
Aucune logique applicative ne doit être insérée ici.

À terme (Milestone 4 ou 5), ce dictionnaire pourra être extrait vers un fichier 
externe (JSON, YAML) ou une interface d'administration (CRUD en base de données), 
permettant aux responsables de maintenance de modifier leurs procédures sans 
requérir de déploiement de code.
"""

DIAGNOSIS_DATABASE = {
    # 1. Problèmes de communication globaux
    "communication_lost": {
        "description": "Perte de connexion avec le datalogger du site. Les données météorologiques et de production ne remontent plus.",
        "recommendation": [
            "Contrôler l'alimentation électrique du coffret de communication",
            "Vérifier la connexion Internet (routeur 4G, carte SIM, crédit Data)",
            "Redémarrer électriquement le datalogger"
        ],
        "severity": "HIGH"
    },

    # 2. Pannes d'équipements majeurs
    "offline_inverter": {
        # Note l'utilisation de {equipment_id} qui sera remplacé dynamiquement
        "description": "L'onduleur {equipment_id} ne communique plus avec le datalogger ou s'est complètement arrêté.",
        "recommendation": [
            "Se rendre sur site et vérifier l'écran / les LEDs de l'onduleur {equipment_id}",
            "Mesurer la tension DC (côté panneaux) aux entrées de l'onduleur",
            "Contrôler l'état du disjoncteur AC principal associé à l'onduleur"
        ],
        "severity": "CRITICAL"
    },
    
    "inverter_overheating": {
        "description": "La température interne de l'onduleur {equipment_id} dépasse le seuil de sécurité, provoquant une baisse volontaire de puissance (Derating).",
        "recommendation": [
            "Contrôler le fonctionnement des ventilateurs de l'onduleur {equipment_id}",
            "Nettoyer les filtres à poussière et les ouïes de ventilation",
            "Vérifier que le local onduleur dispose d'une extraction d'air fonctionnelle"
        ],
        "severity": "HIGH"
    },

    # 3. Anomalies de performance
    "production_anomaly": {
        "description": "La production de la centrale est anormalement faible par rapport à l'ensoleillement et la température mesurés.",
        "recommendation": [
            "Planifier une inspection visuelle de la centrale",
            "Vérifier la présence d'ombrages récents (végétation poussée, objets)",
            "Contrôler le niveau d'encrassement (Soiling) et prévoir un nettoyage des modules si nécessaire"
        ],
        "severity": "MEDIUM"
    },

    # 4. Problèmes de champ DC (Panneaux)
    "dc_string_failure": {
        "description": "Chute soudaine du courant (Ampérage) sur une des entrées. Une chaîne de panneaux (string) est potentiellement coupée.",
        "recommendation": [
            "Localiser la boîte de jonction concernée",
            "Vérifier l'état des fusibles DC",
            "Contrôler visuellement l'intégrité des connecteurs MC4 et des câbles sous les panneaux"
        ],
        "severity": "MEDIUM"
    },
    
    # 5. Fallback par défaut (Si le Decision Engine trouve une règle non documentée)
    "unknown_anomaly": {
        "description": "Une anomalie non répertoriée a été détectée par le moteur de règles ou l'IA.",
        "recommendation": [
            "Consulter les graphiques bruts de puissance et d'irradiation",
            "Contacter un expert de niveau 2 pour une analyse approfondie des données"
        ],
        "severity": "LOW"
    }
}