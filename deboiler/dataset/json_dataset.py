import json
from logging import Logger
from pathlib import Path

from deboiler.dataset.base import DeboilerDataset
from deboiler.logger import logger
from deboiler.models.page import RawPage


@logger
class JsonDataset(DeboilerDataset):
    """
    A json lines dataset.
    """

    logger: Logger

    def __init__(
        self,
        file_path: str | Path,
        content_key: str = "content",
        status_key: str | None = "status",
        content_type_key: str | None = "content_type",
        verbose: bool = True,
    ):
        super().__init__(
            content_key=content_key,
            status_key=status_key,
            content_type_key=content_type_key,
            verbose=verbose,
        )
        self.file_path = Path(file_path)
        self.build_index()

    def build_index(self):
        """
        Builds an index that allows for random access to the records.
        The index is a mapping from url to the record position in the
        input jsonl file (i.e. offset and size).

        It looks like the following:
        {
            "https://www.globality.com": {"offset": XX, "size": XX},
            "https://www.globality.com/about": {"offset": XX, "size": XX},
            ...
        }
        """

        with self.file_path.open("r") as file:
            self.index = dict()

            line = file.readline()
            offset = 0
            while line:
                record = json.loads(line)

                if self.is_valid(record):
                    self.index[record["url"]] = dict(offset=offset, size=file.tell() - offset)

                offset = file.tell()
                line = file.readline()

    @property
    def urls(self):
        return list(self.index.keys())

    def __getitem__(self, url) -> RawPage:
        with self.file_path.open("r") as file:
            file.seek(self.index[url]["offset"])
            line = file.readline()
            record = json.loads(line)
            return RawPage(record["url"], record["content"])

    def __len__(self) -> int:
        return len(self.index)
