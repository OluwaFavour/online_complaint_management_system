from typing import Annotated

from fastapi import Form, UploadFile, File


class ComplaintCreateForm:
    """
    Base class for the ComplaintCreateForm object.

    Attributes:
        type (str): The type of complaint.
        description (str): The description of the complaint.
        supporting_docs (list[UploadFile]): The supporting documents for the complaint.
    """

    def __init__(
        self,
        type: Annotated[str, Form(title="Type of complaint")],
        description: Annotated[str, Form(title="Description of complaint")],
        supporting_docs: Annotated[
            list[UploadFile], File(title="Supporting Documents")
        ] = None,
    ):
        self.type = type
        self.description = description
        self.supporting_docs = supporting_docs
