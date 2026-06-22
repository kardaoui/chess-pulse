from fastapi import APIRouter, HTTPException
import subprocess
import os

router = APIRouter()


@router.post("/")
def sync_parties():
    """
    Déclenche une synchronisation Chess.com.
    Lance load_to_postgres.py dans le container Airflow
    où toutes les dépendances sont installées.
    """
    try:
        result = subprocess.run(
            [
                "docker", "exec",
                "chesspulse_airflow_web",
                "python", "/opt/airflow/ingestion/load_to_postgres.py"
            ],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Échec de la synchronisation",
                    "stderr":  result.stderr
                }
            )

        return {
            "status":  "ok",
            "message": "Synchronisation terminée",
            "output":  result.stdout
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Timeout : la synchronisation a dépassé 5 minutes"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))