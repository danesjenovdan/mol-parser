import logging
import re
from datetime import datetime

import scrapy

from parlaparser import settings


class CommitteeSessionsSpider(scrapy.Spider):
    name = "committee_sessions"
    custom_settings = {
        "ITEM_PIPELINES": {"parlaparser.pipelines.ParlaparserPipeline": 1},
        "CONCURRENT_REQUESTS": "1",
    }
    allowed_domains = ["ljubljana.si"]
    base_url = "https://www.ljubljana.si"
    start_urls = [
        "https://www.ljubljana.si/sl/mestna-obcina/organizacija/mestni-svet-mol/odbori-in-komisije"
    ]

    def __init__(self, parse_name=None, parse_type=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parse_name = parse_name
        self.parse_type = parse_type

    def parse(self, response):
        for li in response.css(".item-title"):
            # paragraph_title = li.css("h3::text").extract_first()
            for body_url in li.css("a::attr(href)").extract():
                yield scrapy.Request(
                    url=self.base_url + body_url,
                    callback=self.parse_body,
                    meta={"classification": "paragraph_title"},
                )

    def parse_body(self, response):
        wb_name = response.css(".header-title-wrapper h1::text").extract_first().strip()
        for li in reversed(response.css("li.list-council-meeting--content--item")):
            date = li.css("div.item-date>p.content::text").extract_first()
            time = li.css("div.item-time>p.content::text").extract_first()
            date = datetime.strptime(date + " " + time, "%d. %m. %Y %H:%M")
            if date < settings.MANDATE_STARTIME:
                continue

            name = li.css("a>strong::text").extract_first()
            if self.parse_name:
                logging.warning(f"{self.parse_name} {self.name}")
                if name != self.parse_name:
                    continue

            time = li.css("div")[2].css("p::text").extract_first()
            session_url = li.css("a::attr(href)").extract_first()
            yield scrapy.Request(
                url=self.base_url + session_url,
                callback=self.parse_session,
                meta={
                    "date": date,
                    "time": time,
                    "session_name": name,
                    "classification": response.meta["classification"],
                    "body_name": wb_name,
                },
            )

    def parse_session(self, response):
        find_enumerating = r"\b(.)\)"
        find_range_enumerating = r"\b(.)\) do \b(.)\)"
        order = 1

        words_orders = ["a", "b", "c", "č", "d", "e", "f", "g", "h", "i", "j", "k"]
        session_name = response.meta["session_name"]
        if self.parse_type in ["speeches", None]:
            docx_files = response.css(".inner .attached-files .docx")
            for docx_file in docx_files:
                if "Magnetogramski zapis" in docx_file.css("::text").extract_first():
                    speeches_file_url = docx_file.css("a::attr(href)").extract_first()

                    yield {
                        "type": "speeches",
                        "docx_url": f"{self.base_url}{speeches_file_url}",
                        "session_name": session_name,
                        "date": response.meta["date"],
                        "time": response.meta["time"],
                        "classification": response.meta["classification"],
                        "body_name": response.meta["body_name"],
                    }

        notes = []
        for link in response.css(".attached-files a"):
            notes.append(
                {
                    "text": link.css("::text").extract_first(),
                    "url": link.css("::attr(href)").extract_first(),
                }
            )

        for doc in response.css("ul.list-files")[-1].css("a"):
            if "Zapisnik" in doc.css("p>span::text").extract_first():
                url = doc.css("::attr(href)").extract_first()
                if url:
                    notes.append(
                        {
                            "url": f"{self.base_url}{url}",
                            "title": doc.css("span::text").extract_first(),
                        }
                    )

        for li in response.css("li.list-published-agendas--item"):
            links = None
            agenda_name_special = li.css(
                ".file-list-header h3.file-list-open-h3::text"
            ).extract_first()
            agenda_name_plain = li.css("span.item-title::text").extract_first()
            links = []
            for link in li.css(".file-list-item a"):
                links.append(
                    {
                        "title": link.css("::text").extract_first(),
                        "url": self.base_url + link.css("::attr(href)").extract_first(),
                    }
                )

            if agenda_name_special:
                agenda_name = agenda_name_special
            else:
                agenda_name = agenda_name_plain.strip()

            data = {
                "type": "committee-agenda-items",
                "notes": notes,
                "session_name": session_name,
                "agenda_name": f"{order}. {agenda_name}",
                "date": response.meta["date"],
                "time": response.meta["time"],
                "classification": response.meta["classification"],
                "body_name": response.meta["body_name"],
                "order": order,
                "links": links,
            }
            order += 1
            yield data
