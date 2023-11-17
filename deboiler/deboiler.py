from collections import defaultdict
from contextlib import contextmanager
from enum import Enum
from functools import lru_cache, partial
from logging import Logger
from multiprocessing import Pool
from time import time
from typing import Iterable, Optional

import langdetect
import numpy as np
from tqdm import tqdm

from deboiler.dataset.base import DeboilerDataset
from deboiler.logger import logger
from deboiler.lxml_query import get_candidate_nodes
from deboiler.models.lxml_node import LxmlTree
from deboiler.models.page import OutputPage, ParsedPage


# Make langdetect deterministic
langdetect.DetectorFactory.seed = 0


class OperationMode(Enum):
    MEMORY = "MEMORY"
    PERFORMANCE = "PERFORMANCE"


@contextmanager
def imap_with_parallel(n_processes, chunksize=None):
    """
    Returns regular `map` if n_processes = 1 else multi-processing `imap`.
    chunksize is only used in the parallel setting.
    """

    if n_processes > 1:
        with Pool(n_processes) as pool:
            yield partial(pool.imap, chunksize=chunksize)
    else:
        yield map


@logger
class Deboiler:
    """
    The main class that implements the boilerplate identification and removal logic.
    """

    logger: Logger

    def __init__(
        self,
        n_processes: int = 1,
        operation_mode: str = "memory",
        # If the iou (for a pair) is more than the given threshold, the two pages
        # are considered almost identical and therefore, that pair is excluded from
        # boilerplate identification.
        iou_threshold: float = 0.95,
        # The number of times a subtree must be shared between pairs to be counted
        # as boilerplate. By default, we consider any shared subtree (min_occurrence_threshold = 1)
        # a boilerplate subtree (as longs as the iou-threshold is not violated for the pair)
        min_occurrence_threshold: int = 1,
        domain: str = "",
        verbose: bool = True,
    ):
        self.domain = domain
        self.operation_mode = OperationMode(operation_mode.upper())
        self.iou_threshold = iou_threshold
        self.min_occurrence_threshold = min_occurrence_threshold
        self.boilerplate_elements: set[str] = set()
        self.n_processes = n_processes
        self.verbose = verbose

        # multi-processing is only available for the memory-optimized mode
        assert self.n_processes >= 1 and (
            self.operation_mode == OperationMode.MEMORY or self.n_processes == 1
        ), "`n_processes` can only be larger than 1 for the `memory` operation mode."

    def fit_parsed_pair(
        self,
        page_pair: tuple[ParsedPage, ParsedPage],
    ) -> tuple[set[str], bool]:
        """
        Finds nodes (i.e. subtrees) that are shared between the input pair (of parsed pages).

        Makes sure the IOU (no of shared nodes over union of nodes) is not above the given
        threshold, in which case does not return any shared nodes. That is a safeguard to
        avoid removing all content in case near-duplicate pages are being compared.
        """

        primary_page, secondary_page = page_pair
        pair_is_too_similar = False

        shared_nodes = primary_page.nodes & secondary_page.nodes
        n_total_nodes = len(primary_page.nodes | secondary_page.nodes)
        iou = len(shared_nodes) / (n_total_nodes if n_total_nodes else 1)

        """
        We process pairs of sorted pages, like the following:

        ('www.globality.com/page-1.html', 'www.globality.com/page-2.html')
        ('www.globality.com/page-2.html', 'www.globality.com/page-3.html')
        ('www.globality.com/page-3.html', 'www.globality.com/page-4.html')
        ...

        Let's assume the input pair to this method is
        ('www.globality.com/page-2.html', 'www.globality.com/page-3.html')
        from the above.

        At this point, the `nodes` cache of the primary page (i.e. page-2) can be emptied,
        since `nodes` is only used during fit and both of the pairs that include page-2
        have already been processed. And that is regardless of the operation mode.

        Whether or not we empty individual LxmlNode caches depends on the operation mode.
        In performance-optimized mode, we intend to keep the parsed object of the page to
        avoid a re-parsing during `transform`.
        In the memory-optimized mode, however, we empty that cache to preserve memory and
        re-parse pages during `transform`.
        """

        if self.operation_mode == OperationMode.MEMORY:
            primary_page.clear_cache(clear_lxml_nodes_cache=True)
        else:
            primary_page.clear_cache(clear_lxml_nodes_cache=False)

        if iou >= self.iou_threshold:
            self.logger.debug(
                f"iou = {iou:.2f} >= {self.iou_threshold:.2f} for urls {primary_page.url}, {secondary_page.url}"
            )
            shared_nodes, pair_is_too_similar = set(), True

        return shared_nodes, pair_is_too_similar

    @lru_cache(maxsize=1)
    def get_parsed_page(self, dataset: DeboilerDataset, url: str) -> ParsedPage:
        """
        Returns the parsed page for the given url.

        In performance mode, parsed pages are cached in the dataset and so that cache
        is used to obtain the parsed page.

        In memory mode, the dataset does not keep a cache, because we don't intend to keep
        parsed pages in memory for long. However, since each page belongs to two pairs, we
        need to keep the parsed page in memory, momentarily, to avoid parsing it twice during
        `fit`. That is why this method uses `lru_cache`. With a cache size of 1, the cache
        only holds on to the last page and replaces it when the next page is parsed.

        Since the lru_cache operates for each process, separately, this caching only works
        as expected when multi-processing is on a batch (by default, the batch size 100).

        To make it clear, consider the following pairs (A, B), (B, C), (C, D), (D, E), (E, F),
        and assume a batch size of 3 with 2 processes.
        In that case, process 1 receives pairs (A, B), (B, C), (C, D) and process 2 receives
        (D, E), (E, F). With lru_cache of size 1, process 1 parses each of A, B, C, and D once
        (It would have parsed B and C twice without lru_cache), and process 2 parses each of
        D, E, and F once. So, when multi-processing is with a batch, caching works as expected.
        Only the pages at the edge of batches (page D in the above) will be parsed twice, which
        will be negligible when the batch size is big enough.
        """

        return dataset.parse_page(url)

    def fit_pair(
        self, url_pair: tuple[str, str], dataset: DeboilerDataset
    ) -> tuple[set[str], bool]:
        """
        Finds nodes that are shared between the input pair (of string urls).
        Unlike the `fit_parsed_pair` that cannot be parallelized (since Lxml objects
        are not picklable), this method can.
        """

        primary_url, secondary_url = url_pair
        return self.fit_parsed_pair(
            (
                self.get_parsed_page(dataset, primary_url),
                self.get_parsed_page(dataset, secondary_url),
            )
        )

    def fit(self, dataset: DeboilerDataset, chunksize: int = 100) -> None:
        """
        Given a dataset, identifies all boilerplate elements used in the domain.
        """

        boilerplate_elements_counter: dict = defaultdict(int)
        n_similar_pairs = 0
        start_time = time()

        if self.operation_mode == OperationMode.PERFORMANCE:
            dataset.cache_pages()

        with imap_with_parallel(self.n_processes, chunksize=chunksize) as imap:
            for shared_nodes, pair_is_too_similar in tqdm(
                imap(partial(self.fit_pair, dataset=dataset), dataset.pairs),
                desc=f"Identifying boilerplate elements {self._domain_desc}",
                total=len(dataset) - 1,  # no of pairs = no of urls - 1
                disable=not self.verbose,
            ):
                n_similar_pairs += int(pair_is_too_similar)
                for node in shared_nodes:
                    boilerplate_elements_counter[node] += 1

        self.boilerplate_elements = {
            node
            for node, occurrence_count in boilerplate_elements_counter.items()
            if occurrence_count >= self.min_occurrence_threshold
        }

        self.logger.debug(
            (
                f"Number of shared elements that did not meet the occurrence threshold {self._domain_desc}: "
                f"{len(boilerplate_elements_counter) - len(self.boilerplate_elements)}"
            )
        )
        self.logger.debug(
            (
                f"Number of similar pairs that were excluded from boilerplate identification {self._domain_desc}: "
                f"{n_similar_pairs:,}"
            )
        )
        self.logger.info(
            (
                f"Total number of boilerplate elements found for the domain {self._domain_desc}: "
                f"{len(self.boilerplate_elements):,}"
            )
        )
        self.logger.info(
            f"Boilerplate identification took {time() - start_time:,.1f} seconds {self._domain_desc}"
        )

    @classmethod
    def detect_language(cls, page: LxmlTree, cleaned_text: str) -> Optional[str]:
        """
        First, tries to detect language based on page metadata.
        If that is not available, uses the heuristic detection algorithm from langdetect.
        """

        meta_language = page.root.language
        if not bool(cleaned_text):
            return None
        return meta_language or langdetect.detect(cleaned_text)

    def transform_parsed_page(
        self, page: ParsedPage, include_cleaned_html: bool = False
    ) -> OutputPage:
        """
        Cleans the input parsed page by removing boilerplate elements and extracts multiple attributes
        (e.g. text, lists, headings, etc.).
        Note that the page transformation happens in place (i.e. the input page does change).
        """

        # Since the changes are in-place, anything that is meant to be extracted from the
        # original page should be extracted before page is cleaned.
        # We get title and breadcrumbs from the original page, and other attributes from
        # the cleaned page.

        text = page.content.root.extract_text()
        title = page.content.root.extract_title()
        breadcrumbs = page.content.root.extract_breadcrumbs()

        # Find elements matching boilerplate elements
        nodes_to_be_removed = {
            node
            for node in get_candidate_nodes(page.content)
            if node.normalized_representation() in self.boilerplate_elements
        }
        for node in nodes_to_be_removed:
            node.remove()

        cleaned_text = page.content.root.extract_text()
        output_page = OutputPage(
            url=page.url,
            text=text,
            cleaned_text=cleaned_text,
            title=title,
            headings=page.content.root.extract_headings(),
            lists=page.content.root.extract_lists(),
            breadcrumbs=breadcrumbs,
            language=self.detect_language(page.content, cleaned_text),
            cleaned_html=page.content.root.get_html() if include_cleaned_html else None,
        )

        page.clear_cache(clear_lxml_nodes_cache=True)

        return output_page

    def transform_page(
        self, url: str, dataset: DeboilerDataset, include_cleaned_html: bool = False
    ) -> OutputPage:
        """
        Cleans the input page (defined by its url) by removing boilerplate elements and
        extracts multiple attributes (e.g. text, lists, headings, etc.).

        Unlike the `transform_parsed_page` method that cannot be parallelized (since LXML
        objects cannot be pickled), this method can.
        """

        return self.transform_parsed_page(dataset.parse_page(url), include_cleaned_html)

    @property
    def _domain_desc(self):
        return f"({self.domain})" if self.domain else "for domain"

    def transform(
        self, dataset: DeboilerDataset, chunksize: int = 100, include_cleaned_html: bool = False
    ) -> Iterable[OutputPage]:
        """
        Transforms the input dataset and yields an OutputPage object for each page.
        If include_cleaned_html = True, the output also includes the html version of
        the cleaned page.
        """

        if self.operation_mode == OperationMode.PERFORMANCE:
            try:
                assert len(dataset.cached_pages) == len(dataset)
            except AssertionError:
                raise AssertionError(
                    (
                        "In `performance` mode, the same dataset passed to the `fit` method should be "
                        "passed to the `transform` method"
                    )
                )

        start_time = time()
        page_len_delats = []
        with imap_with_parallel(self.n_processes, chunksize=chunksize) as imap:
            for output_page in tqdm(
                imap(
                    partial(
                        self.transform_page,
                        dataset=dataset,
                        include_cleaned_html=include_cleaned_html,
                    ),
                    dataset.urls,
                ),
                desc=f"Cleaning pages {self._domain_desc}",
                total=len(dataset),
                disable=not self.verbose,
            ):
                page_len_delats.append(len(output_page.text) - len(output_page.cleaned_text))
                yield output_page

        self.logger.info(f"Page cleaning and text extraction stats {self._domain_desc}:")
        self.logger.info(f"  * Number of pages: {len(page_len_delats):,}")
        self.logger.info(f"  * Time taken: {time() - start_time:,.1f} seconds")
        self.logger.info(
            (
                "  * Noise reduction per page (characters): "
                f"{np.mean(page_len_delats):.1f} mean, {np.median(page_len_delats):.1f} median"
            )
        )
