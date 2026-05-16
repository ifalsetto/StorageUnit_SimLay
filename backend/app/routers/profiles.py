from pathlib import Path
from fastapi import APIRouter
from app.core.config import CONFIG_DIR, load_all_config

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

@router.get("")
def list_profiles():
    profiles = []
    for path in (CONFIG_DIR / "profiles").glob("*_profile.json"):
        profiles.append(path.stem.replace("_profile", ""))
    return {"profiles": sorted(profiles)}

@router.get("/{profile_name}")
def get_profile(profile_name: str):
    config = load_all_config(profile_name)
    return config["profile"]
