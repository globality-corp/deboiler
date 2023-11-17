from string import Template

import pytest

from deboiler import Deboiler
from deboiler.models.page import ParsedPage


template = Template(
    """
    <!DOCTYPE html>
    <html dir="rtl" $language prefix="og: http://ogp.me/ns#">
        <head>
            <title>$title</title>
        </head>
        <body>
            <div>$text</div>
        </body>
    </html>
    """
)

TEXT = "this is a long enough text"
examples = [
    # non-english from meta
    (
        template.substitute(language='lang="he-IL"', title="page title", text=TEXT),
        "he-il",
    ),
    # english from meta
    (
        template.substitute(language='lang="en"', title="page title", text=TEXT),
        "en",
    ),

    # english with locale from meta
    (
        template.substitute(language='lang="en-us"', title="page title", text=TEXT),
        "en-us",
    ),

    # english from text
    (
        template.substitute(language="", title="page title", text=TEXT),
        "en",
    ),

    # non-english from text
    (
        template.substitute(language="", title="título de la página", text="algún texto"),
        "es",
    ),
]


@pytest.mark.parametrize("html, expected_language", examples)
def test_language_detection(html, expected_language):
    page = ParsedPage(url="https://www.foo.com", content=html)
    text = page.content.root.extract_text()
    language = Deboiler.detect_language(page.content, text)
    assert language == expected_language
