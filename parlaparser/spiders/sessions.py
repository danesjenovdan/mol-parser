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

    def __init__(self, parse_name=None, parse_type=None, *args,**kwargs):
        super().__init__(*args, **kwargs)
        self.parse_name = parse_name
        self.parse_type = parse_type

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
        find_enumerating = r'\b(.)\)'
        find_range_enumerating = r'\b(.)\) do \b(.)\)'
        order = 0
        words_orders = ['a', 'b', 'c', 'č', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k']
        session_name = response.css(".header-holder h1::text").extract_first()
        if self.parse_type in ['speeches', None]:
            docx_files = response.css(".inner .attached-files .docx")
            for docx_file in docx_files:
                if 'Magnetogramski zapis' in docx_file.css('::text').extract_first():
                    speeches_file_url = docx_file.css('a::attr(href)').extract_first()

                    yield {
                        'type': 'speeches',
                        'docx_url': f'{self.base_url}{speeches_file_url}',
                        'session_name': session_name,
                        'date': response.meta["date"],
                        'time': response.meta["time"]
                    }

        for li in response.css(".list-agenda>li"):
            agenda_name = li.css('.file-list-header h3.file-list-open-h3::text').extract_first()
            if self.parse_type in ['questions', None]:
                if agenda_name and agenda_name.strip() == 'Vprašanja in pobude svetnikov ter odgovori na vprašanja in pobude':
                    for link in li.css('.file-list-item a'):
                        text = link.css('::text').extract_first()
                        url = link.css('::attr(href)').extract_first()

                        yield {
                            'type': 'question',
                            'text': text,
                            'session_name': session_name,
                            'agenda_name': agenda_name,
                            'date': response.meta["date"],
                            'time': response.meta["time"],
                            'url': url
                        }
            if self.parse_type in ['votes', None]:
                votes = {}
                links = []
                for link in li.css('.file-list-item a'):
                    link_text = link.css('::text').extract_first()
                    link_url = link.css('::attr(href)').extract_first()
                    enums = re.findall(find_enumerating, link_text)
                    range_enums = re.findall(find_range_enumerating, link_text)
                    if range_enums:
                        enums = words_orders[words_orders.index(range_enums[0][0]):words_orders.index(range_enums[0][1])+1]
                    if 'Glasovan' in link_text:
                        order += 1
                        vote_link = link.css('::attr(href)').extract_first()
                        if enums:
                            enum = enums[0]
                        else:
                            enum = 0

                        votes[enum] = {
                            'type': 'vote',
                            'pdf_url': f'{self.base_url}{link_url}',
                            'session_name': session_name,
                            'agenda_name': agenda_name,
                            'date': response.meta["date"],
                            'time': response.meta["time"],
                            'order': order
                        }
                    else:
                        links.append({
                            'title': link_text,
                            'url': f'{self.base_url}{link_url}',
                            'enums': enums
                        })
                for key, vote in votes.items():
                    if key == 0:
                        tmp_links = links
                    else:
                        tmp_links = [link for link in links if key in link['enums']]
                    vote.update({
                        'links': tmp_links
                    })
                    yield vote

