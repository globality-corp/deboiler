from logging import Logger

from deboiler.dataset.base import DeboilerDataset
from deboiler.logger import logger
from deboiler.models.page import RawPage


@logger
class ListDataset(DeboilerDataset):
    """
    A simple list dataset used mostly in tests.
    """

    logger: Logger

    def __init__(
        self,
        records: list[dict],
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
        self.records = records
        self.build_index()

    def build_index(self):
        """
        Builds an index that allows for random access of the records.
        The index is a mapping from url to record number.
        """

        self.index = dict()
        for n, record in enumerate(self.records):
            if self.is_valid(record):
                self.index[record["url"]] = n

    @property
    def urls(self):
        return list(self.index.keys())

    def __getitem__(self, url) -> RawPage:
        record = self.records[self.index[url]]
        return RawPage(record["url"], record["content"])

    def __len__(self) -> int:
        return len(self.index)
