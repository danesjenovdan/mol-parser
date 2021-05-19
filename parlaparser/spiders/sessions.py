from datetime import datetime

from parlaparser import settings

import scrapy
import re
import logging


class SessionsSpider(scrapy.Spider):
    name = 'sessions'
    custom_settings = {
        'ITEM_PIPELINES': {
            'parlaparser.pipelines.ParlaparserPipeline': 1
        },
        'CONCURRENT_REQUESTS': '1'
    }
    allowed_domains = ['ljubljana.si']
    base_url = 'https://www.ljubljana.si'
    start_urls = ['https://www.ljubljana.si/sl/mestni-svet/seje-mestnega-sveta/']

    def __init__(self, parse_name=None, *args,**kwargs):
        super().__init__(*args, **kwargs)
        self.parse_name = parse_name

    def parse(self, response):
        for li in reversed(response.css("#page-content .ul-table li")):
            date = li.css("div")[1].css('p::text').extract_first()
            date = datetime.strptime(date, '%d. %m. %Y')
            if date < settings.MANDATE_STARTIME:
                continue

            name = li.css("div")[0].css('a::text').extract_first()
            if self.parse_name:
                logging.warning(f'{self.parse_name} {self.name}')
                if name != self.parse_name:
                    continue


            time = li.css("div")[2].css('p::text').extract_first()
            session_url = li.css("div")[0].css('a::attr(href)').extract_first()
            yield scrapy.Request(
                url=self.base_url + session_url,
                callback=self.parse_session,
                meta={'date': date, 'time': time})

    def parse_session(self, response):
        session_name = response.css(".header-holder h1::text").extract_first()
        docx_files = response.css(".inner .attached-files .docx")
        for docx_file in docx_files:
            if 'Magnetogramski zapis' in docx_file.css('::text').extract_first():
                speeches_file_url = docx_file.css('a::attr(href)').extract_first()
                # TODO remove this when vote paser is done
                yield {
                    'type': 'speeches',
                    'docx_url': f'{self.base_url}{speeches_file_url}',
                    'session_name': session_name,
                    'date': response.meta["date"],
                    'time': response.meta["time"]
                }

        for li in response.css(".list-agenda>li"):
            agenda_name = li.css('.file-list-header h3.file-list-open-h3::text').extract_first()
            for link in li.css('.file-list-item a'):
                if 'Glasovan' in link.css('::text').extract_first():
                    vote_link = link.css('::attr(href)').extract_first()
                    yield {
                        'type': 'vote',
                        'pdf_url': f'{self.base_url}{vote_link}',
                        'session_name': session_name,
                        'agenda_name': agenda_name,
                        'date': response.meta["date"],
                        'time': response.meta["time"]
                    }

