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

    # parse vote from attachment section
    def parse_attachment_vote(self, response, section_name):
        parse_agenda_item_vote = False
        # find votings of agenda items
        if self.parse_type in ['votes', None]:
            for child in response.css('div.inner>*'):
                if parse_agenda_item_vote:
                    links = []
                    for link in child.css('a'):
                        link_text = link.css('::text').extract_first()
                        link_url = link.css('::attr(href)').extract_first()
                        if 'Glasovan' in link_text:
                            return {
                                'type': 'vote',
                                'pdf_url': f'{self.base_url}{link_url}',
                                'session_name': self.session_name,
                                'agenda_name': None,
                                'date': response.meta["date"],
                                'time': response.meta["time"],
                                'order': self.order,
                                'session_notes': self.session_notes,
                                'links': links
                            }
                            self.order += 1
                        else:
                            links.append({
                                'tag': section_name,
                                'title': link_text,
                                'url': f'{self.base_url}{link_url}',
                                'enums': 0
                            })
                if child.css('::text').extract_first() == section_name:
                    parse_agenda_item_vote = True

    def parse_session(self, response):
        find_enumerating = r'\b(.)\)'
        find_range_enumerating = r'\b(.)\) do \b(.)\)'
        words_orders = ['a', 'b', 'c', 'č', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k']
        session_name = response.css(".header-holder h1::text").extract_first()
        self.session_name = session_name
        self.session_notes = {}

        for doc in response.css('ul.attached-files')[-1].css('a'):
            if 'Zapisnik' in doc.css('::text').extract_first():
                self.session_notes = {
                    'url': f'{self.base_url}{doc.css("::attr(href)").extract_first()}',
                    'title': doc.css('::text').extract_first()
                }

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
                        'time': response.meta["time"],
                        'session_notes': self.session_notes
                    }

        self.order = 1
        self.li_order = 1

        yield self.parse_attachment_vote(response, 'Sprejeti dnevni red')

        for li in response.css(".list-agenda>li"):
            agenda_name = li.css('.file-list-header h3.file-list-open-h3::text').extract_first()
            # get agenda_names: is using for a) b) c)....
            agenda_names = li.css('.file-list-header h3.file-list-open-h3::text').extract()
            agenda_names = list(map(str.strip, agenda_names))
            text_agenda_name = li.css('div>h3::text').extract_first()
            is_added_agenda_item = False

            notes = {}
            if agenda_name and agenda_name.strip() == 'Vprašanja in pobude svetnikov ter odgovori na vprašanja in pobude':
                if self.parse_type in ['questions', None]:
                    for link in li.css('.file-list-item a'):
                        text = link.css('::text').extract_first()
                        url = link.css('::attr(href)').extract_first()
                        is_added_agenda_item = True
                        yield {
                            'type': 'question',
                            'text': text,
                            'session_name': session_name,
                            'agenda_name': f'{self.li_order}. {agenda_name}',
                            'date': response.meta["date"],
                            'time': response.meta["time"],
                            'url': url,
                            'session_notes': self.session_notes,
                            'order': self.order
                        }
                        self.order += 1
            if self.parse_type in ['votes', None]:
                votes = {}
                links = []
                for list_item in li.css('.file-list-item'):
                    group = list_item.css('h4::text').extract_first()
                    for link in list_item.css('a'):
                        link_text = ' '.join(link.css('::text').extract()).strip()
                        link_url = link.css('::attr(href)').extract_first()
                        enums = re.findall(find_enumerating, link_text)
                        range_enums = re.findall(find_range_enumerating, link_text)
                        if range_enums:
                            enums = words_orders[words_orders.index(range_enums[0][0]):words_orders.index(range_enums[0][1])+1]
                        if 'Glasovan' in link_text:
                            self.order += 1
                            vote_link = link.css('::attr(href)').extract_first()
                            if enums:
                                enum = enums[0]
                            else:
                                enum = 0

                            # if agenda item is enumerated, then try to find correct name
                            if link_text[1] == ')':
                                for temp_agenda_name in agenda_names:
                                    if temp_agenda_name and temp_agenda_name[0] == link_text[0]:
                                        agenda_name = temp_agenda_name

                            votes[enum] = {
                                'type': 'vote',
                                'pdf_url': f'{self.base_url}{link_url}',
                                'session_name': session_name,
                                'agenda_name': f'{self.li_order}. {agenda_name}',
                                'date': response.meta["date"],
                                'time': response.meta["time"],
                                'order': self.order,
                                'session_notes': self.session_notes
                            }
                        else:
                            links.append({
                                'tag': group,
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
                    is_added_agenda_item = True

                # if agenda item has documents and dont have votes (document Glasovanje)
                if is_added_agenda_item == False and len(agenda_names) > 1:
                    agenda_names_fixed = []
                    for item in agenda_names:
                        if item[1] != ")":
                            agenda_names_fixed[-1] += f' {item}'
                        else:
                            agenda_names_fixed.append(item)
                    for agenda_name in agenda_names_fixed:
                        current_enum = agenda_name[0]
                        agenda_links = []
                        for link in links:
                            if current_enum in link['enums']:
                                agenda_links.append(link)
                        yield {
                            'type': 'agenda-item',
                            'session_name': session_name,
                            'agenda_name': f'{self.li_order}. {agenda_name}',
                            'date': response.meta["date"],
                            'time': response.meta["time"],
                            'session_notes': self.session_notes,
                            'order': self.order,
                            'links': agenda_links
                        }
                        self.order += 1
                        is_added_agenda_item = True

            if not is_added_agenda_item:
                # If agenda name is not url
                if not agenda_names:
                    agenda_names = [text_agenda_name]
                for agenda_name in agenda_names:
                    yield {
                        'type': 'agenda-item',
                        'session_name': session_name,
                        'agenda_name': f'{self.li_order}. {agenda_name}',
                        'date': response.meta["date"],
                        'time': response.meta["time"],
                        'session_notes': self.session_notes,
                        'order': self.order,
                        'links': []
                    }

                    self.order += 1
            self.li_order += 1

        yield self.parse_attachment_vote(response, 'Razširitev dnevnega reda')
