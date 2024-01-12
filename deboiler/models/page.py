import re
from dataclasses import dataclass
from io import StringIO
from logging import Logger

from lxml.etree import HTMLParser, _Element, parse as parse_html

from deboiler.logger import logger
from deboiler.lxml_query import get_candidate_nodes
from deboiler.models.lxml_node import LxmlTree


EMPTY_HTML = "<html></html>"


@dataclass
class RawPage:
    """
    A crawled page with raw (string or binary) content.
    """

    url: str
    content: bytes | str

    def __repr__(self):
        return f"RawPage(url={self.url}, content={self.content[:20]}...)"

    def parse(self):
        return ParsedPage(self.url, self.content)


@logger
class ParsedPage:
    """
    A parsed page.

    It stores the parsed version (as an LxmlTree) of the given raw content.
    nodes attribute is a cache of string representations for all the candidate nodes (subtrees)
    in this page.
    """

    logger: Logger
    parser = HTMLParser(remove_comments=True)

    def __init__(self, url: str, content: bytes | str):
        self.url = url
        self.content: LxmlTree = self.parse(content)
        self.nodes: set[str] = {
            # Set of normalized representations for all candidate nodes in the LxmlTree
            node.normalized_representation()
            for node in get_candidate_nodes(self.content)
        }

    def __repr__(self):
        return f"ParsedPage(url={self.url})"

    def parse(self, content: str | bytes) -> LxmlTree:
        """
        Parses the input html string/bytes into an LxmlTree.
        """

        # TODO - Is decoding necessary or can we directly parse the bytes object?
        # https://github.com/globality-corp/deboiler/pull/1#discussion_r916847537
        decoded_content = self._decode_content(content) if isinstance(content, bytes) else content
        parsed_content = self._parse_string(decoded_content)
        if not isinstance(parsed_content, _Element):
            self.logger.warning(f"Parsed content for url is not of type _Element: {self.url}")
            return LxmlTree(self._parse_string(EMPTY_HTML))
        return LxmlTree(parsed_content)

    def _decode_content(self, content: bytes) -> str:
        """
        Decodes the bytes content by trying different encodings (in the order of popularity).
        """

        encodings = ["UTF-8", "ISO-8859-1", "ASCII"]
        for encoding in encodings:
            try:
                return content.decode(encoding)
            except Exception:
                continue
        self.logger.warning(f"Failed to decode {self.url}")
        return self._decode_content(EMPTY_HTML.encode())

    def _parse_string(self, content: str) -> _Element:
        """
        Parses the string content into an LXML _Element.
        """

        def warn_and_return(error):
            self.logger.warning(f"Failed to parse {self.url}")
            self.logger.warning(repr(error))
            return self._parse_string(EMPTY_HTML)

        try:
            return parse_html(StringIO(content), self.parser).getroot()

        except ValueError:
            try:
                # Unicode strings with encoding declaration are not supported (by lxml).
                # We get rid of the declaration by:
                #  a. Finding the encoding declaration
                #  b. Finding the first open tag < after the encoding declaration
                encoding_position = next(re.finditer("encoding[ ]*=", content)).end()
                return parse_html(
                    # fmt: off
                    StringIO(content[content.find("<", encoding_position):]),
                    # fmt: on
                    self.parser,
                ).getroot()
            except Exception as error:
                warn_and_return(error)

        except Exception as error:
            warn_and_return(error)

    def clear_cache(self, clear_lxml_nodes_cache: bool):
        """
        Depending on the input binary flag, this method can clear one or both of the following:

        a) `nodes` attribute of this class: `nodes` contains string representations for all candidate
           subtrees in the page. It is only used during `fit`. So, it can be empties after the page is
           used during `fit`.
        b) Cache of individual constituent `LxmlNode`s: Each `LxmlNode` object has a cache that contains
           its string representation, and is needed during both `fit` and `transform`.

        If clear_lxml_nodes_cache = False: Only clears the former cache.
        Otherwise: Clears both caches.
        """

        self.nodes = set()
        if clear_lxml_nodes_cache:
            self.content.clear_cache()


@dataclass
class OutputPage:
    """
    All content extracted from a page
    """

    url: str
    text: str
    cleaned_text: str
    title: str
    headings: str
    lists: str
    breadcrumbs: str
    language: str | None = None
    cleaned_html: str | None = None
