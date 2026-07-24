"""
Module principal d'orchestration (main.py).
Exécute le pipeline séquentiel de Milestone 1 :
Initialisation -> Connexion BDD -> Création des tables ->
Collecte des données (Rawametrix & Energysoft) -> Persistance via Repository.
Aucun calcul ni détection d'anomalie n'est effectué à cette étape.
"""

import pandas as pd
from app.config.settings import settings
from app.utils.logger import logger
from app.database.database import engine, Base, get_db_session
from app.database.repository import DatabaseRepository
from app.collectors.rawametrix import RawametrixClient
from app.collectors.energysoft import EnergysoftClient
from requests.exceptions import RequestException, HTTPError


def run_pipeline() -> None:
    """Exécute l'ensemble du pipeline d'ingestion et de sauvegarde des données."""
    logger.info("=== DÉMARRAGE DU PIPELINE DE SUPERVISION (MILESTONE 1) ===")

    # 1. Création des tables en base de données
    logger.info("Création des tables de la base de données...")
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception as drop_exc:
        logger.warning(f"Impossible de supprimer les tables existantes : {drop_exc}")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables créées ou vérifiées avec succès.")

    # 2. Initialisation des clients API
    logger.info("Initialisation des clients API Rawametrix et Energysoft...")
    rawa_client = RawametrixClient()
    es_client = EnergysoftClient()

    # 3. Ouverture de la session de base de données via le Repository
    db_session = next(get_db_session())
    repo = DatabaseRepository(db_session)

    try:
        # 4. Téléchargement et sauvegarde de la liste des centrales (Rawametrix)
        logger.info("Téléchargement de la liste des centrales (Rawametrix)...")
        try:
            df_plants = rawa_client.get_plants()
        except (HTTPError, RequestException) as exc:
            logger.warning(f"Impossible de récupérer la liste des centrales depuis Rawametrix : {exc}")
            logger.warning("Le pipeline se termine sans collecte de données car l'API Rawametrix n'est pas disponible.")
            return
        
        if not df_plants.empty:
            plants_dict_list = df_plants.to_dict(orient="records")
            repo.save_plants(plants_dict_list)
        else:
            logger.warning("Aucune centrale récupérée depuis Rawametrix.")
            return

        # Récupération des centrales enregistrées pour itérer sur leurs mesures/pertes/onduleurs
        from app.database.models import Plant
        all_plants = db_session.query(Plant).all()

        for plant in all_plants:
            logger.info(f"Traitement pour la centrale : {plant.name} (ID interne: {plant.id}, Rawa ID: {plant.rawametrix_id})")

            try:
                # 5. Téléchargement et sauvegarde des mesures journalières
                df_measures = rawa_client.get_day_measures(plant_id=plant.rawametrix_id)
                if not df_measures.empty:
                    measures_list = df_measures.to_dict(orient="records")
                    repo.save_measures(plant_id=plant.id, measures_data=measures_list)

                # 6. Téléchargement et sauvegarde des pertes
                df_losses = rawa_client.get_losses(plant_id=plant.rawametrix_id)
                if not df_losses.empty:
                    losses_list = df_losses.to_dict(orient="records")
                    repo.save_losses(plant_id=plant.id, losses_data=losses_list)

                # 7. Téléchargement et sauvegarde des onduleurs (Energysoft)
                es_site_id = plant.rawametrix_id  # identifiant de référence fourni par Rawametrix, utilisé comme indice de recherche
                try:
                    df_inverters = es_client.get_inverters(site_id=es_site_id, site_name=plant.name)
                except (HTTPError, RequestException) as exc:
                    logger.warning(f"Impossible de récupérer les onduleurs Energysoft pour la centrale {plant.name} ({plant.id}) : {exc}")
                    df_inverters = pd.DataFrame()

                if not df_inverters.empty:
                    inverters_list = df_inverters.to_dict(orient="records")
                    repo.save_inverters(plant_id=plant.id, inverters_data=inverters_list)
            except Exception as exc:
                logger.warning(f"Échec du traitement de la centrale {plant.name} ({plant.id}) : {exc}")
                continue

        logger.info("=== PIPELINE TERMINÉ AVEC SUCCÈS ===")

    except Exception as e:
        logger.error(f"Erreur critique lors de l'exécution du pipeline : {e}")
        db_session.rollback()
    finally:
        db_session.close()


if __name__ == "__main__":
    run_pipeline()