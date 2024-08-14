import asyncio
from typing import Any

from cloudinary.uploader import upload
from cloudinary.api import delete_resources_by_prefix, delete_folder

from fastapi import HTTPException, status


async def upload_image(asset_folder: str, image: Any) -> str:
    try:
        response = upload(
            image,
            asset_folder=asset_folder,
            use_asset_folder_as_public_id_prefix=True,
            use_filename=True,
            allowed_formats="pdf,png,jpg,jpeg,mp4",
        )
        url = response["secure_url"]
        return url
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error occurred while uploading image: {e}",
        )


async def delete_folder_by_prefix(prefix: str) -> None:
    try:
        delete_resources_by_prefix(prefix)
        delete_folder(prefix)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error occurred while deleting folder: {e}",
        )
