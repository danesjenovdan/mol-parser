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

    def __init__(self, parse_name=None, agenda_name=None, parse_type=None, *args,**kwargs):
        super().__init__(*args, **kwargs)
        self.parse_name = parse_name
        self.parse_type = parse_type
        self.agenda_name = agenda_name
        self.find_enumerating = r'\b(.)\)'
        self.find_range_enumerating = r'\b(.)\) do \b(.)\)'
        self.words_orders = ['a', 'b', 'c', 'č', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k']

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
                    print(f'pass session {name} because {self.parse_name}')
                    continue


            time = li.css("div")[2].css('p::text').extract_first()
            session_url = li.css("div")[0].css('a::attr(href)').extract_first()
            yield scrapy.Request(
                url=self.base_url + session_url,
                callback=self.parse_session,
                meta={'date': date, 'time': time})

    # parse vote from attachment section
    def parse_attachment_vote(self, response, section_name, order, session_name, session_notes, basic_vote_data):
        parse_agenda_item_vote = False
        # find votings of agenda items
        votes = {}
        links = []
        agenda_names = [section_name]
        if self.parse_type in ['votes', None]:
            for child in response.css('div.inner>*'):
                # parse votes from agneda items
                if parse_agenda_item_vote:
                    links = []

                    for link in child.css('a'):
                        link_text, link_url, enums = self.find_links_and_enums(link)

                        order = self.initiate_vote_or_link(
                            votes,
                            links,
                            link_text,
                            link_url,
                            enums,
                            agenda_names,
                            basic_vote_data,
                            section_name,
                            None,
                            order
                        )

                current_section = child.css('::text').extract_first()
                if current_section == section_name:
                    parse_agenda_item_vote = True
                elif current_section in ['', None]:
                    pass
                else:
                    parse_agenda_item_vote = False


        tmp = self.update_votes_with_links(votes, links)

        votes = votes.values()
        if votes:
            all_links = []
            all_urls = []
            for vote in votes:
                if section_name == 'Sprejeti dnevni red':
                    # dont create agneda item for Sprejeti dnevni red
                    vote['agenda_name'] = None
                for link in vote['links']:
                    if link['url'] not in all_urls:
                        all_urls.append(link['url'])
                        all_links.append(link)
            agenda_item = {
                    'type': 'agenda-item',
                    'agenda_name': section_name,
                    'order': order,
                    'links': all_links
                }
            agenda_item.update(basic_vote_data)
        else:
            agenda_item = None
        return votes, agenda_item

    # parse vote which is positioned in header
    def parse_voting_for_guest_free_and_presession_votes(self, response, basic_vote_data):
        votes = {}
        header_links = response.css('div.inner>p').css('a')
        for link in header_links:
            try:
                link_text = link.css('::text').extract_first()
            except:
                link_text = ''
            if link_text == 'Glasovanje, da seja poteka brez navzočnosti občanov':
                vote_link = link.css('::attr(href)').extract_first()
                order = self.initiate_vote_or_link(
                    votes,
                    [],
                    'Glasovanje, da seja poteka brez navzočnosti občanov',
                    vote_link,
                    [],
                    ['Glasovanje, da seja poteka brez navzočnosti občanov'],
                    basic_vote_data,
                    '',
                    -1,
                    -2,
                )
            elif link_text in ['Glasovanje', 'Glasovanji', 'Glasovanja']:
                vote_link = link.css('::attr(href)').extract_first()
                order = self.initiate_vote_or_link(
                    votes,
                    [],
                    'Glasovanje',
                    vote_link,
                    [],
                    ['Pred prvo točko dnevnega reda'],
                    basic_vote_data,
                    '',
                    -2,
                    -3,
                )
        return votes


    def parse_session(self, response):
        session_name = response.css(".header-holder h1::text").extract_first().strip()
        session_notes = {}
        votes = {}
        print(session_name)

        for doc in response.css('ul.attached-files')[-1].css('a'):
            if 'Zapisnik' in doc.css('::text').extract_first():
                session_notes = {
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
                        'session_notes': session_notes
                    }

        order = 1
        li_order = 1

        basic_vote_data = {
            'session_notes': session_notes,
            'session_name': session_name.strip(),
            'date': response.meta["date"],
            'time': response.meta["time"],
        }

        votes = self.parse_voting_for_guest_free_and_presession_votes(response, basic_vote_data)
        for vote in votes.values():
            vote['agenda_name'] = None
            vote['links'] = []
            yield vote

        parsed_votes, agenda_item = self.parse_attachment_vote(response, 'Sprejeti dnevni red', -1, session_name, session_notes, basic_vote_data)
        for vote in parsed_votes:
            yield vote

        for li in response.css(".list-agenda>li"):
            agenda_name = li.css('.file-list-header h3.file-list-open-h3::text').extract_first()
            if self.agenda_name and self.agenda_name != agenda_name:
                continue
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
                            'agenda_name': f'{li_order}. {agenda_name}',
                            'date': response.meta["date"],
                            'time': response.meta["time"],
                            'url': url,
                            'session_notes': session_notes,
                            'order': order
                        }
                        order += 1
            if self.parse_type in ['votes', None]:
                votes = {}
                links = []
                for list_item in li.css('.file-list-item'):
                    group = list_item.css('h4::text').extract_first()
                    for link in list_item.css('a'):

                        link_text, link_url, enums = self.find_links_and_enums(link)

                        order = self.initiate_vote_or_link(
                            votes,
                            links,
                            link_text,
                            link_url,
                            enums,
                            agenda_names,
                            basic_vote_data,
                            group,
                            li_order,
                            order
                        )

                is_added_agenda_item = self.update_votes_with_links(votes, links, is_added_agenda_item)

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
                            'agenda_name': f'{li_order}. {agenda_name}',
                            'date': response.meta["date"],
                            'time': response.meta["time"],
                            'session_notes': session_notes,
                            'order': order,
                            'links': agenda_links
                        }
                        order += 1
                        is_added_agenda_item = True
            for vote in votes.values():
                yield vote

            if not is_added_agenda_item:
                # If agenda name is not url
                if not agenda_names:
                    agenda_names = [text_agenda_name]
                for agenda_name in agenda_names:
                    yield {
                        'type': 'agenda-item',
                        'session_name': session_name,
                        'agenda_name': f'{li_order}. {agenda_name}',
                        'date': response.meta["date"],
                        'time': response.meta["time"],
                        'session_notes': session_notes,
                        'order': order,
                        'links': []
                    }

                    order += 1
            li_order += 1

        parsed_votes, agenda_item = self.parse_attachment_vote(response, 'Razširitev dnevnega reda', order, session_name, session_notes, basic_vote_data)
        if agenda_item:
            yield agenda_item
        for vote in parsed_votes:
            yield vote

    def find_links_and_enums(self, link):
        link_text = ' '.join(link.css('::text').extract()).strip()
        link_url = link.css('::attr(href)').extract_first()
        enums = re.findall(self.find_enumerating, link_text)
        range_enums = re.findall(self.find_range_enumerating, link_text)
        if range_enums:
            enums = self.words_orders[self.words_orders.index(range_enums[0][0]):self.words_orders.index(range_enums[0][1])+1]

        return link_text, link_url, enums

    def initiate_vote_or_link(self, votes, links, link_text, link_url, enums, agenda_names, basic_vote_data, group, li_order, order):
        """
        This method create votes and links and prepares enumerating objects.
        """
        if 'Glasovan' in link_text:
            if enums:
                enum = enums[0]
            else:
                enum = 0

            agenda_name = agenda_names[0] if agenda_names else ''

            # if agenda item is enumerated, then try to find correct name
            if link_text[1] == ')':
                for temp_agenda_name in agenda_names:
                    if temp_agenda_name and temp_agenda_name[0] == link_text[0]:
                        agenda_name = temp_agenda_name

            if li_order and agenda_name:
                full_agenda_name = f'{li_order}. {agenda_name}'
            else:
                full_agenda_name = agenda_name
            new_vote = {
                'type': 'vote',
                'pdf_url': f'{self.base_url}{link_url}',
                'agenda_name': full_agenda_name,
                'order': order,
            }
            new_vote.update(basic_vote_data)

            links.append({
                'tag': 'vote-pdf',
                'title': link_text,
                'url': f'{self.base_url}{link_url}',
                'enums': enums
            })

            votes[enum] = new_vote
            order += 1
        else:
            links.append({
                'tag': group,
                'title': link_text,
                'url': f'{self.base_url}{link_url}',
                'enums': enums
            })
        return order

    def update_votes_with_links(self, votes, links, is_added_agenda_item=False):
        """
        This method find enumerated links and add it to vote
        """
        for key, vote in votes.items():
            if key == 0:
                tmp_links = links
            else:
                # add also non enumerated docs
                tmp_links = list(filter(lambda link: link['enums'] == [], links))
                tmp_links = tmp_links + [link for link in links if key in link['enums']]
            votes[key].update({
                'links': tmp_links
            })
            #return vote
            is_added_agenda_item = True
        return is_added_agenda_item
