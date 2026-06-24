import asyncio
import os
from fastapi import APIRouter, HTTPException
from loguru import logger

router = APIRouter(prefix="/deploy", tags=["deploy"])

DEPLOY_SCRIPT = os.path.expanduser("~/scripts/deploy.sh")


@router.get("/")
async def run_deploy():
    if not os.path.exists(DEPLOY_SCRIPT):
        logger.error(f"Deploy failed — script not found at {DEPLOY_SCRIPT}")
        raise HTTPException(status_code=404, detail="Shell script file not found.")

    logger.info(f"Deploy triggered — running script {DEPLOY_SCRIPT}")

    try:
        process = await asyncio.create_subprocess_exec(
            DEPLOY_SCRIPT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(
                f"Deploy script failed — return_code={process.returncode} stderr={stderr.decode().strip()}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Script failed: {stderr.decode().strip()}",
            )

        logger.info(
            f"Deploy successful — return_code={process.returncode} output={stdout.decode().strip()}"
        )
        return {
            "status": "success",
            "return_code": process.returncode,
            "output": stdout.decode().strip(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deploy unexpected error — {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
