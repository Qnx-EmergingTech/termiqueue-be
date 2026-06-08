import asyncio
import os
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/deploy", tags=["deploy"])

DEPLOY_SCRIPT = os.path.expanduser("~/scripts/deploy.sh")


@router.get("/")
async def run_deploy():
    if not os.path.exists(DEPLOY_SCRIPT):
        raise HTTPException(status_code=404, detail="Shell script file not found.")

    try:
        process = await asyncio.create_subprocess_exec(
            DEPLOY_SCRIPT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Script failed: {stderr.decode().strip()}",
            )

        return {
            "status": "success",
            "return_code": process.returncode,
            "output": stdout.decode().strip(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
