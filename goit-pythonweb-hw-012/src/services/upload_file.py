"""Cloudinary file-upload adapter for user avatars."""

import cloudinary
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError
from fastapi import UploadFile


class UploadFileError(RuntimeError):
    """Raised when the external upload service rejects an avatar upload."""

    pass


class UploadFileService:
    """Cloudinary upload adapter."""

    def __init__(self, cloud_name: str, api_key: str, api_secret: str):
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )

    @staticmethod
    def upload_file(file: UploadFile, username: str) -> str:
        """Upload a user avatar and return a Cloudinary URL.

        The image is cropped to a 250 × 250 thumbnail on Cloudinary's
        edge servers.

        :param file: The uploaded file from the HTTP request.
        :type file: UploadFile
        :param username: Used to build a stable Cloudinary public ID.
        :type username: str
        :returns: The HTTPS URL of the transformed image.
        :rtype: str
        :raises UploadFileError: If Cloudinary rejects the upload.
        """
        public_id = f"ContactsAPI/{username}"
        try:
            response = cloudinary.uploader.upload(
                file.file,
                public_id=public_id,
                overwrite=True,
            )
        except CloudinaryError as err:
            raise UploadFileError("Avatar upload failed") from err

        return cloudinary.CloudinaryImage(public_id).build_url(
            width=250,
            height=250,
            crop="fill",
            version=response.get("version"),
        )
