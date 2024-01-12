from abc import ABC, abstractmethod, abstractproperty
from collections.abc import Mapping

from tqdm import tqdm

from deboiler.models.page import ParsedPage, RawPage


class DeboilerDataset(ABC):
    """
    Base dataset class.

    To create custom dataset, one needs to sub-class from this base class and
    implement `__getitem__` and `__len__` methods, as well as the `urls` property.
    In that implementation, it is usually beneficial to create an index of the data
    during class instantiation that allows for random access to records in `__getitem__`.
    Refer to deboiler/dataset/json_dataset.py for an example.
    """

    def __init__(
        self,
        content_key: str | None = "content",
        status_key: str | None = "status",
        content_type_key: str | None = "content_type",
        verbose: bool = True,
    ):
        self.cached_pages: Mapping[str, ParsedPage] = dict()
        self.content_key = content_key
        self.status_key = status_key
        self.content_type_key = content_type_key
        self.verbose = verbose

    @abstractmethod
    def __getitem__(self, url: str) -> RawPage:
        pass

    @abstractmethod
    def __len__(self):
        pass

    @abstractproperty
    def urls(self):
        pass

    @property
    def pairs(self) -> list[tuple[str, str]]:
        """
        Returns a list of url pairs (as string tuples).
        These pairs are the ones that are compared for boilerplate identification.

        """

        if len(self.urls) < 2:
            return []

        sorted_urls = sorted(self.urls)
        return [
            (sorted_urls[n], sorted_urls[n + 1])
            for n in range(len(sorted_urls) - 1)
        ]

    def cache_pages(self):
        """
        Parses and caches all pages in the dataset.
        It is used in the `performance` mode of the `deboiler`.
        """

        self.cached_pages = {
            url: self[url].parse()
            for url in tqdm(
                self.urls,
                desc="Parsing and caching pages",
                disable=not self.verbose,
            )
        }

    def parse_page(self, url: str):
        """
        Gets the page with the given url and returns its parsed object.
        If the parsed object is already cached, returns it from the cache,
        otherwise, parses and returns it.

        NOTE: It does NOT add any pages to the cache. Caching only happens
        when the `cache_pages` method is called.
        """

        if url in self.cached_pages:
            return self.cached_pages[url]
        return self[url].parse()

    def is_valid(self, record):
        return (
            # Ensure successful page crawl
            (not self.status_key or 200 <= record.get(self.status_key) < 300)
            and
            # Ensure text/html content-type
            (not self.content_type_key or record.get(self.content_type_key) == "text/html")
            and
            # Ensure bytes or string content object type
            isinstance(record["content"], (bytes, str))
        )
