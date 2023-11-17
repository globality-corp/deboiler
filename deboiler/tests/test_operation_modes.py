from unittest.mock import patch

import pytest

from deboiler import Deboiler
from deboiler.dataset import ListDataset
from deboiler.models.page import ParsedPage, RawPage


@pytest.mark.parametrize("operation_mode", ["memory", "performance"])
def test_pipeline_end_to_end(operation_mode):
    # `parse_counter` defined as global, so it can be changed within the `gen_mocked_page` function
    global parse_counter
    parse_counter = 0

    base_url = "http://www.globality.com"
    html_content = "<html></html>"
    pages_count = 10

    def gen_mocked_page():
        global parse_counter
        parsed_page = ParsedPage(url=f"{base_url}/{parse_counter}", content=html_content)
        parse_counter += 1
        return parsed_page

    with patch.object(RawPage, "parse") as mocked:
        mocked.side_effect = gen_mocked_page

        dataset = ListDataset(
            [
                dict(url=f"{base_url}/{n}", status=200, content=html_content)
                for n in range(pages_count)
            ],
            content_type_key=None,
        )

        deboiler = Deboiler(
            # Mocking does not work on multi-processing
            # To test memory-optimized mode with multi-processing,
            # we should rely on manual testing
            n_processes=1,
            operation_mode=operation_mode,
        )

        # During fit, each page should be parsed one time
        # So, we expect parse_counter == pages_count
        assert parse_counter == 0
        deboiler.fit(dataset)
        assert parse_counter == pages_count

        # During transform in memory-optimized mode, each page will be
        # parsed again. So we expect parse_counter == pages_count
        # For performance-optimized mode, however, parsed pages should be
        # cached during fit and reused during transform.
        # So, we expect parse_counter == 0
        parse_counter = 0
        output_pages = list(deboiler.transform(dataset))
        assert len(output_pages) == pages_count
        assert parse_counter == (operation_mode == "memory") * pages_count
