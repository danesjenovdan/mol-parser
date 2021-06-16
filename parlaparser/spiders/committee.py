import scrapy
import re


class CommitteeSpider(scrapy.Spider):
    name = 'committee'
    custom_settings = {
        'ITEM_PIPELINES': {
            'parlaparser.pipelines.ParlaparserPipeline': 1
        },
        'CONCURRENT_REQUESTS': '1'
    }
    allowed_domains = ['ljubljana.si']
    base_url = 'https://www.ljubljana.si'
    start_urls = ['https://www.ljubljana.si/sl/mestni-svet/odbori-in-komisije/']

    def parse(self, response):
        for party_link in response.css(".sub-navigation-list a::attr(href)").extract():
            yield scrapy.Request(url=self.base_url + party_link, callback=self.parse_orgs)

    def parse_orgs(self, response):
        org_name = response.css(".header-holder h1::text").extract_first().strip()

        classification = self.parse_classification(org_name)

        role = None
        people = []

        for html_line in response.css(".block_area_aside .content-toggle")[1].css("::text").extract():
            html_line = html_line.replace(':', '').replace(',', '').replace('-', '').strip()
            if html_line == '':
                continue
            if html_line.strip().lower().startswith('predsedni') or \
               html_line.strip().lower().startswith('podpredsedni') or \
               html_line.strip().lower().startswith('člani') or \
               html_line.strip().lower().startswith('strokovni sodelavec') or \
               html_line.strip().lower().startswith('strokovna sodelavka'):
                if role:
                    for person in people:
                        yield {
                            'type': 'memberships',
                            'name': person.strip(),
                            'org_name': org_name,
                            'role': self.parse_role(role.strip().lower()),
                            'classification': classification
                        }
                    people = []
                role = html_line.strip()
            else:
                people.append(html_line.strip())
        for person in people:
            yield {
                'type': 'memberships',
                'name': person.strip(),
                'org_name': org_name,
                'role': self.parse_role(role.strip().lower()),
                'classification': classification
            }

    def parse_role(self, data):
        if data.startswith('predsedni'):
            return 'president'
        elif data.startswith('podpredsedni'):
            return 'vice president'
        elif data.startswith('člani'):
            return 'member'
        elif data.startswith('strokovn'):
            return 'expert'
        return data


    def parse_classification(self, data):
        if 'Komisija' in data:
            return 'commision'
        if 'Odbor' in data:
            return 'committee'
        return 'other'
