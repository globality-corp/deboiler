"""
The AvroDataset class will be removed from the package.
"""

from logging import Logger
from pathlib import Path
from typing import Optional

from fastavro import reader

from deboiler.dataset.base import DeboilerDataset
from deboiler.logger import logger
from deboiler.models.page import RawPage


@logger
class AvroDataset(DeboilerDataset):
    logger: Logger

    def __init__(
        self,
        file_path: str,
        content_key: str = "content",
        status_key: Optional[str] = "status",
        content_type_key: Optional[str] = "content_type",
        verbose: bool = True,
    ):
        super().__init__(verbose=verbose)
        self.file_path = Path(file_path)
        self.content_key = content_key
        self.status_key = status_key
        self.content_type_key = content_type_key
        self.build_index()

    def build_index(self):
        """
        Builds an index that allows for random access of the objects.
        The index is a dictionary that looks like the following:

        {
            "https://www.globality.com": {"offset": XX, "size": XX},
            "https://www.globality.com/about": {"offset": XX, "size": XX},
            ...
        }

        """
        with self.file_path.open("rb") as file:
            # Read in the header information on reader initialization, which will correctly
            # position the file pointer at the start of the first record
            file.seek(0)
            avro_reader = reader(file)

            offset = file.tell()
            self.index = dict()
            for record in avro_reader:
                if self.is_valid(record):
                    self.index[record["url"]] = dict(offset=offset, size=file.tell() - offset)

                offset = file.tell()

    @property
    def urls(self):
        return list(self.index.keys())

    def __getitem__(self, url) -> RawPage:
        with self.file_path.open("rb") as file:
            file.seek(0)
            avro_reader = reader(file)
            next(avro_reader)
            file.seek(self.index[url]["offset"])
            try:
                record = next(avro_reader)
            except ValueError:
                # The first record of each file will fail with a ValueError,
                # so we fix this manually
                # TODO - Can we somehow make it more elegant by not failing in the first record?
                file.seek(0)
                avro_reader = reader(file)
                record = next(avro_reader)
            return RawPage(record["url"], record["content"])

    def __len__(self) -> int:
        return len(self.index)
