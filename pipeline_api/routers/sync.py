from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import logging
import os

import httpx

router = APIRouter()
logger = logging.getLogger(__name__)

DAG_ID = "chesspulse_pipeline"


def _config():
    """Configuration de l'API Airflow, lue dans l'environnement."""
    url = os.getenv("AIRFLOW_API_URL")
    user = os.getenv("AIRFLOW_ADMIN_USER")
    password = os.getenv("AIRFLOW_ADMIN_PASSWORD")

    if not all([url, user, password]):
        raise HTTPException(
            status_code=503,
            detail="Déclenchement indisponible : configuration Airflow absente",
        )
    return url, (user, password)


@router.post("/")
def sync_parties():
    """
    Déclenche le DAG d'ingestion via l'API REST d'Airflow.

    L'implémentation précédente lançait `docker exec` depuis l'intérieur du
    conteneur. Elle ne fonctionnait pas — ni binaire docker, ni socket monté —
    et la faire fonctionner aurait imposé de monter /var/run/docker.sock,
    c'est-à-dire d'accorder un accès équivalent à root sur l'hôte à un service
    HTTP. Passer par l'API d'Airflow conserve l'orchestrateur comme unique
    point d'exécution des tâches.
    """
    url, auth = _config()
    horodatage = datetime.now(timezone.utc).isoformat()

    try:
        reponse = httpx.post(
            f"{url}/dags/{DAG_ID}/dagRuns",
            json={"dag_run_id": f"sync_api__{horodatage}"},
            auth=auth,
            timeout=30,
        )
    except httpx.RequestError as e:
        logger.exception("Airflow injoignable")
        raise HTTPException(
            status_code=502, detail="Airflow injoignable"
        ) from e

    if reponse.status_code == 409:
        raise HTTPException(
            status_code=409, detail="Une synchronisation est déjà en cours"
        )

    if reponse.status_code >= 400:
        logger.error(
            "Déclenchement refusé par Airflow (%s) : %s",
            reponse.status_code, reponse.text,
        )
        raise HTTPException(
            status_code=502, detail="Le déclenchement du DAG a échoué"
        )

    corps = reponse.json()
    return {
        "status": "declenche",
        "dag_run_id": corps.get("dag_run_id"),
        "etat": corps.get("state"),
        "message": "Synchronisation lancée — suivre la progression dans Airflow",
    }
