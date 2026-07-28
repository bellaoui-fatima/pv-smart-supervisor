"""
Module principal d'orchestration du Milestone 2 (main.py).
Exécute le pipeline séquentiel complet :
Collecte -> Preprocessing -> Expected Production -> String Analysis -> 
Feature Engineering -> Feature Store (Persistance SQLAlchemy).
"""

import pandas as pd
from sqlalchemy import text
from requests.exceptions import RequestException, HTTPError

from app.config.settings import settings
from app.utils.logger import logger
from app.database.database import engine, Base, get_db_session
from app.database.repository import DatabaseRepository
from app.database.models import Plant
from app.collectors.rawametrix import RawametrixClient
from app.collectors.energysoft import EnergysoftClient

# Modules de traitement du Milestone 2
from app.processing.preprocessing import DataPreprocessor
from app.processing.expected_production import ExpectedProductionCalculator
from app.processing.strings_analysis import StringAnalyzer
from app.processing.feature_engineering import FeatureEngineer
from app.processing.feature_store import FeatureStore


def _ensure_daily_measure_columns() -> None:
    """Ajoute automatiquement les colonnes manquantes à la table daily_measures."""
    with engine.begin() as connection:
        existing_columns = {
            row[1].lower() for row in connection.execute(text("PRAGMA table_info(daily_measures)"))
        }

        required_columns = {
            "performance_ratio",
            "temperature_gap",
            "irradiation_ratio",
            "loss_percentage",
            "offline_inverters",
            "failed_strings",
            "communication_status",
            "rolling_mean_7d",
            "rolling_std_7d",
            "anomaly_score_rule",
        }

        missing_columns = required_columns - existing_columns
        for column_name in sorted(missing_columns):
            connection.execute(text(f"ALTER TABLE daily_measures ADD COLUMN {column_name} FLOAT"))


def run_pipeline() -> None:
    """Exécute l'ensemble du pipeline de Feature Engineering et de stockage."""
    logger.info("=== DÉMARRAGE DU PIPELINE DE FEATURE ENGINEERING (MILESTONE 2) ===")

    # 1. Initialisation / Vérification de la base de données
    logger.info("Vérification des tables de la base de données...")
    try:
        # Remarque : En production, privilégier Alembic pour les migrations.
        # Base.metadata.drop_all(bind=engine) # Décommenter en dev si besoin de reset complet
        Base.metadata.create_all(bind=engine)
        _ensure_daily_measure_columns()
        logger.info("Tables vérifiées/créées avec succès.")
    except Exception as exc:
        logger.error(f"Erreur lors de la préparation des tables : {exc}")
        return

    # 2. Initialisation des clients d'API
    logger.info("Initialisation des clients API...")
    rawa_client = RawametrixClient()
    es_client = EnergysoftClient()

    # 3. Initialisation des modules de traitement
    preprocessor = DataPreprocessor()
    prod_calculator = ExpectedProductionCalculator()
    string_analyzer = StringAnalyzer()
    feature_engineer = FeatureEngineer()

    # 4. Ouverture de la session BDD, du Repository et du FeatureStore
    db_session = next(get_db_session())
    repo = DatabaseRepository(db_session)
    feature_store = FeatureStore(repo)

    try:
        # 5. Collecte et sauvegarde de la liste des centrales
        logger.info("Étape 1 : Collecte de la liste des centrales (Rawametrix)...")
        try:
            df_plants = rawa_client.get_plants()
        except (HTTPError, RequestException) as exc:
            logger.error(f"Impossible de récupérer les centrales depuis Rawametrix : {exc}")
            return

        if df_plants is None or df_plants.empty:
            logger.warning("Aucune centrale récupérée. Fin du pipeline.")
            return

        repo.save_plants(df_plants.to_dict(orient="records"))
        all_plants = db_session.query(Plant).all()

        # 6. Traitement centrale par centrale
        for plant in all_plants:
            logger.info(f"--- Traitement de la centrale : {plant.name} (ID DB: {plant.id}) ---")

            try:
                # --- A. Collecte des données brutes ---
                logger.info("1/6. Collecte des données brutes API...")
                df_measures = rawa_client.get_day_measures(plant_id=plant.rawametrix_id)
                df_losses = rawa_client.get_losses(plant_id=plant.rawametrix_id)

                try:
                    df_inverters = es_client.get_inverters(site_id=plant.rawametrix_id, site_name=plant.name)
                except Exception as exc:
                    logger.warning(f"Onduleurs Energysoft indisponibles pour {plant.name} : {exc}")
                    df_inverters = pd.DataFrame()

                # Tentative de récupération des mesures de strings (si supporté par le client)
                try:
                    df_strings = rawa_client.get_string_measures(plant_id=plant.rawametrix_id)
                except AttributeError:
                    # Si l'API ou la méthode dédiée n'existe pas encore
                    df_strings = pd.DataFrame()

                # --- B. Preprocessing ---
                logger.info("2/6. Nettoyage et validation des données (Preprocessing)...")
                df_clean_measures = preprocessor.process_daily_measures(df_measures)

                if df_clean_measures.empty:
                    logger.warning(f"Aucune mesure valide à traiter pour la centrale {plant.name}.")
                    continue

                # --- C. Expected Production ---
                logger.info("3/6. Calcul de la production attendue, delta et PR...")
                df_expected_measures = prod_calculator.process(df_clean_measures)

                # --- D. String Analysis ---
                logger.info("4/6. Analyse du parc de chaînes (Strings)...")
                string_results = string_analyzer.analyze(df_strings)

                # --- E. Feature Engineering ---
                logger.info("5/6. Construction de la matrice de Features pour l'IA...")
                df_features = feature_engineer.create_features(
                    df_measures=df_expected_measures,
                    inverters_data=df_inverters,
                    losses_data=df_losses,
                    string_analysis=string_results
                )

                # --- F. Persistance via Feature Store & Repository ---
                logger.info("6/6. Persistance des features et entités dans la base de données...")
                
                # Sauvegarde des objets bruts complémentaires
                if not df_losses.empty:
                    repo.save_losses(plant_id=plant.id, losses_data=df_losses.to_dict(orient="records"))
                if not df_inverters.empty:
                    repo.save_inverters(plant_id=plant.id, inverters_data=df_inverters.to_dict(orient="records"))

                # Sauvegarde des features enrichies via le FeatureStore
                feature_store.save_features(plant_id=plant.id, df_features=df_features)

                logger.info(f"Traitement réussi pour la centrale : {plant.name}")

            except Exception as exc:
                logger.error(f"Échec du traitement pour la centrale {plant.name} : {exc}", exc_info=True)
                continue

        logger.info("=== PIPELINE DU MILESTONE 2 TERMINÉ AVEC SUCCÈS ===")

    except Exception as e:
        logger.critical(f"Erreur critique lors de l'exécution du pipeline : {e}", exc_info=True)
        db_session.rollback()
    finally:
        db_session.close()


if __name__ == "__main__":
    run_pipeline()