import cloudinary
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError
from fastapi import UploadFile


class UploadFileError(RuntimeError):
    pass


class UploadFileService:
    def __init__(self, cloud_name: str, api_key: str, api_secret: str):
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )

    @staticmethod
    def upload_file(file: UploadFile, username: str) -> str:
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
