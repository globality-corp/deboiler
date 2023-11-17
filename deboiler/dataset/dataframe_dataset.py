from logging import Logger
from typing import Optional

import pandas as pd

from deboiler.dataset.base import DeboilerDataset
from deboiler.logger import logger
from deboiler.models.page import RawPage


@logger
class DataFrameDataset(DeboilerDataset):
    """
    A dataset made of a Pandas dataframe.
    """

    logger: Logger

    def __init__(
        self,
        records: pd.DataFrame,
        content_key: str = "content",
        status_key: Optional[str] = "status",
        content_type_key: Optional[str] = "content_type",
        verbose: bool = True,
    ):
        super().__init__(
            content_key=content_key,
            status_key=status_key,
            content_type_key=content_type_key,
            verbose=verbose,
        )
        for column in ["url", "content", self.status_key, self.content_type_key]:
            if column:
                assert column in records.columns, f"Missing column '{column}' in dataframe"
        self.records = records
        self.build_index()

    def build_index(self):
        """
        Builds an index that allows for random access of the records.
        The index is a mapping from url to record number.
        """
        self.index = dict()
        for n, record in self.records.iterrows():
            if self.is_valid(record):
                self.index[record["url"]] = n

    @property
    def urls(self):
        return list(self.index.keys())

    def __getitem__(self, url) -> RawPage:
        record = self.records.iloc[self.index[url]]
        return RawPage(record["url"], record["content"])

    def __len__(self) -> int:
        return len(self.index)
