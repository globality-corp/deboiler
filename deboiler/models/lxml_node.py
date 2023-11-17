import cgi
import re
import unicodedata
from logging import debug
from typing import (
    Generator,
    Mapping,
    Optional,
    Union,
)

from lxml.etree import _Comment, _Element, _ElementTree
from lxml.html import tostring as html_tostring


# When extracting text from html, line breaks are NOT added before texts from these tags
INLINE_ELEMENTS = {
    "a",
    "span",
    "em",
    "strong",
    "u",
    "i",
    "font",
    "mark",
    "label",
    "s",
    "sub",
    "sup",
    "tt",
    "bdo",
    "button",
    "cite",
    "del",
    "b",
}


"""
The character indicating list elements in the extracted text.

For instance if LIST_INDICATOR_CHAR = "*", the extracted text from:

This is a list:
<ul>
  <li> item 1
  <li> item 2
</ul>

will be:

This is a list
* item 1
* item 2

"""
LIST_INDICATOR_CHAR = "*"

# No text will be extracted from these blacklisted tags
BLACKLIST_TAGS = {"script", "style", "noscript", "cyfunction", "button", "form"}
BLACKLIST_CLASSES = (_Comment,)

# Added to the html dom to uniquely identify an element
NODE_IDENTIFIER_KEY = "__node_id"


class LxmlTree:
    """
    A wrapper around the LXML _Element object of a parsed page
    """

    def __init__(self, tree: _Element):
        if not isinstance(tree, _Element):
            raise ValueError("non _Element passed")

        self.tree = tree

        # Store a mapping of IDs to their LxmlNode wrapped objects
        self.elements: Mapping[str, LxmlNode] = {}

        # For each element, add a unique element
        for i, node in enumerate(self.tree.iter()):
            node_id = str(i)
            node.attrib[NODE_IDENTIFIER_KEY] = node_id
            self.elements[node_id] = LxmlNode(node, tree=self)

    @property
    def root(self):
        return self.lxml_to_node(self.tree)

    def clear_cache(self):
        for element in self.elements.values():
            element.clear_cache()

    def xpath(self, *args, **kwargs):
        results = self.tree.xpath(*args, **kwargs)
        return self.lxml_to_nodes(results)

    def lxml_to_nodes(self, elements: list[_Element]) -> list["LxmlNode"]:
        """
        Converter class to take a list of lxml elements and
        return a list of wrapper LxmlNode from our central registry.
        """

        return [
            node
            for element in elements
            for node in [self.lxml_to_node(element)]
            if node is not None
        ]

    def lxml_to_node(self, element: _Element) -> Optional["LxmlNode"]:
        # We occasionally see elements that don't have an ID set; this is often
        # due to some synthetic lxml objects like _ProcessingInstruction being
        # found in the tree but refusing to save attrib changes that are attempted
        # in the __init__ function of this tree class
        #
        # In these cases log a warning and bail out
        if NODE_IDENTIFIER_KEY not in element.attrib:
            debug(f"Unfound element: {element}")
            return None

        return self.elements[element.attrib[NODE_IDENTIFIER_KEY]]


class LxmlNode:
    """
    A wrapper around an Lxml _Element node that owns several method to extract
    title, text, headings, lists, breadcrumbs, etc.
    """

    def __init__(self, node: Union[_ElementTree, _Element], tree: LxmlTree):
        self.node = node
        self.tree = tree  # page tree

        self._normalized_representation_cache: Optional[str] = None

    def __iter__(self):
        for child in self.node:
            yield self.tree.lxml_to_node(child)

    @staticmethod
    def _normalize_attributes(attributes: dict) -> str:
        """
        Creates a normalized string representation for the input dict of attributes.
        At this point, we ignore tag attributes entirely, so it returns an empty string.
        """

        return ""

    @property
    def attrib(self) -> dict:
        attributes = {**self.node.attrib}
        del attributes[NODE_IDENTIFIER_KEY]
        return attributes

    @property
    def text(self) -> str:
        return self.node.text

    @property
    def tail(self) -> str:
        return self.node.tail

    @property
    def tag(self) -> str:
        return self.node.tag

    def getchildren(self) -> list["LxmlNode"]:
        return self.tree.lxml_to_nodes(self.node.getchildren())

    def clear_cache(self):
        self._normalized_representation_cache = None

    def _remove_spaces(self, text: str) -> str:
        return (
            text
            .replace("\t", "")
            .replace("\n", "")
            .replace(" ", "")
            .lower()
            .strip()
        )

    def normalized_representation(self, is_root: bool = True) -> str:
        """
        Returns the normalized representation of the node.

        The outcome does not have to be proper html or even human-readable.
        It only needs to be the same for the nodes that are similar (structurally and textually).
        """

        # We only want the elements within the root DOM, not what comes after
        tailing_text = self._remove_spaces(self.tail.strip() if (not is_root and self.tail) else "")

        if self._normalized_representation_cache:
            return self._normalized_representation_cache + tailing_text

        self._normalized_representation_cache = self._remove_spaces(
            self._normalized_representation()
        )
        return self._normalized_representation_cache + tailing_text

    def _normalized_representation(self) -> str:
        """
        Generates the normalized string representation of the node, recursively.

        This representation is ONLY intended to compare nodes with each other.
        It is NOT intended to create the proper HTML representation of a node, as it
        may not produce correct HTML code in some cases.

        Tag attributes are ignored in this representation, which results in the
        following two nodes being the same:
        node_1 = <a href="link" >Share this content</a>
        node_2 = <a href="a-different-link" >Share this content</a>
        """

        attribute_string = self._normalize_attributes(self.attrib)

        text = self.text.strip() if self.text else ""

        if not self.getchildren() and not text:
            return f"<{self.tag}{attribute_string}></{self.tag}>"

        internal_elements = "".join(
            [child.normalized_representation(is_root=False) for child in self.getchildren()]
        )
        optional_text_space = ""
        return f"<{self.tag}{attribute_string}>{text}{optional_text_space}{internal_elements}</{self.tag}>"

    @staticmethod
    def _normalize_string(text: Optional[str], lower_case: bool = False) -> str:
        """
        Normalizes an input string by removing extra spaces, tabs, multiple new lines, etc.
        """

        if text is None:
            return ""

        text = cgi.html.unescape(text)  # type: ignore
        text = unicodedata.normalize("NFKC", text)  # type: ignore
        text = text.lower() if lower_case else text
        text = re.sub("\t", " ", text)
        text = re.sub("\n[ ]+", "\n", text)
        text = re.sub("[ ]+", " ", text)
        text = re.sub("[\n]{3,}", "\n\n", text)  # 3 or more new lines --> just 2 new lines
        text = "\n".join(
            line.strip()
            for line in text.split("\n")
            if line.strip()
        )
        return text.strip()

    def get_html(self):
        """
        Produces a proper html for the node.
        """

        return html_tostring(self.node).decode()

    def remove(self) -> None:
        """
        Removes the node.
        (based on https://stackoverflow.com/a/53572856)
        """

        parent = self.node.getparent()
        if parent is None:
            return
        if self.node.tail and self.node.tail.strip():
            prev = self.node.getprevious()
            if prev is not None:
                prev.tail = (prev.tail or "") + self.node.tail
            else:
                parent.text = (parent.text or "") + self.node.tail
        parent.remove(self.node)

    def _extract_text(self, node: _Element) -> Generator[str, None, None]:
        """
        Extracts the text from the input node (and its children).

        It does not extract any text from blacklisted tags (BLACKLIST_TAGS, BLACKLIST_CLASSES).
        It does not add line breaks before INLINE_ELEMENTS to maintain text continuity.

        (Inspired by the code from https://stackoverflow.com/a/66835172)
        """

        for child in node:
            if child.tag in BLACKLIST_TAGS or isinstance(child, BLACKLIST_CLASSES):
                continue

            # if the tag is a block type tag then yield new lines before after
            is_block_element = child.tag not in INLINE_ELEMENTS

            if is_block_element:
                yield "\n"

            if child.tag == "li":
                yield f"{LIST_INDICATOR_CHAR} "

            if child.text and child.text.strip():
                yield child.text

            yield from (["\n"] if child.tag == "br" else self._extract_text(child))

            if child.tail and child.tail.strip():
                yield child.tail

            if is_block_element:
                yield "\n"

    def extract_text(self, get_body: bool = True) -> str:
        """
        Extracts the node's text.
        """

        node = self.node
        if get_body:
            body = node.xpath("//*[self::body]")
            if not body:
                return ""
            node = body[0]

        text = "".join(self._extract_text(node))
        return self._normalize_string(text)

    def extract_lists(self) -> str:
        """
        Finds all <ul> and <ol> items in the node.
        Returns all of them as a concatenated string.
        """

        lists_of_items = self.node.xpath("//*[self::ul or self::ol]")
        lists_of_items = ["".join(self._extract_text(ul)).strip() for ul in lists_of_items]
        return self._normalize_string("\n\n".join(lists_of_items))

    def extract_title(self) -> str:
        title = self.node.xpath("//*[self::title]")
        return self._normalize_string(title[0].text if title else "")

    def extract_headings(self) -> str:
        """
        Finds all headings in the node.
        Returns all of them as a concatenated string.
        """

        headings = self.node.xpath(
            # More info here: https://stackoverflow.com/a/26951465
            "//*[re:test(local-name(), '^h[1-6]$')]",
            namespaces={"re": "http://exslt.org/regular-expressions"},
        )
        return self._normalize_string(
            "\n".join(
                [
                    heading.text.strip()
                    for heading in headings
                    if heading.text and heading.text.strip()
                ]
            )
        )

    def extract_breadcrumbs(self) -> str:
        """
        Finds breadcrumbs in the node.
        Returns all of them as a concatenated string.
        """

        # 200 characters max len to make sure a big node is not mistakenly picked up
        max_breadcrumbs_len = 200

        # The domain coverage for the below regex, based on ~130 therapeutic providers is 47%.
        for breadcrumb_xpath_pattern in [
            # xpath pattern based on: https://stackoverflow.com/a/7405471/4155071
            # search for a node that has ANY attribute containing a specific string
            "//*[@*[contains(., 'breadcrumbs')]]",
            "//*[@*[contains(., 'breadcrumb')]]",
            "//*[@*[contains(., 'crumb')]]",
        ]:
            breadcrumb_elements = [
                element
                for element in self.node.xpath(breadcrumb_xpath_pattern)
                if element.tag != "body"
            ]
            if breadcrumb_elements:
                # try to match in order, from most restrict to the least restrict pattern
                break

        if not breadcrumb_elements:
            return ""

        breadcrumbs = [
            "".join(self._extract_text(breadcrumb_element)).strip()
            for breadcrumb_element in breadcrumb_elements
        ]
        # in case multiple items are found, we return the most complete one, i.e. the longest one,
        # as long as it is shorter than the max length threshold
        breadcrumbs_meeting_len_criteria = sorted(
            [
                bc
                for bc in breadcrumbs
                if len(bc) <= max_breadcrumbs_len
            ],
            key=len,
        )

        if breadcrumbs_meeting_len_criteria:
            return breadcrumbs_meeting_len_criteria[-1]

        return ""

    @property
    def language(self) -> str:
        """
        Detects the language based on the metadata.
        If it cannot find it, returns None.
        """

        meta_lang = getattr(self.node, "attrib", {}).get("lang")
        return meta_lang.lower() if meta_lang else None
