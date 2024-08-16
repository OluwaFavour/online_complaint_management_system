from typing import Any

from cloudinary.uploader import upload
from cloudinary.api import delete_resources_by_prefix, delete_folder

from fastapi import HTTPException, status


async def upload_image(asset_folder: str, image: Any) -> str:
    """
    Uploads an image to the cloud storage.

    Args:
        asset_folder (str): The folder in the cloud storage where the image will be stored.
        image (Any): The image to be uploaded.

    Returns:
        str: The URL of the uploaded image.

    Raises:
        HTTPException: If an internal server error occurs while uploading the image.
    """
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
    """
    Delete a folder and its contents in the cloud storage system based on the given prefix.

    Args:
        prefix (str): The prefix used to identify the folder and its contents.

    Raises:
        HTTPException: If an internal server error occurs while deleting the folder.

    Returns:
        None
    """
    try:
        delete_resources_by_prefix(prefix)
        delete_folder(prefix)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error occurred while deleting folder: {e}",
        )
