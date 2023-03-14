from parlaparser.data_parsers.base_parser import BaseParser
from parlaparser import settings

from datetime import datetime, timedelta

import logging


class CommitteeSessionParser(BaseParser):
    def __init__(self, data, data_storage):
        super().__init__(data_storage)

        # {
        #     'type': 'agenda-items',
        #     'notes': [
        #         {
        #             'text': 'Zapisnik 2. seje OGDTK',
        #             'url': '/assets/Uploads/Zapisnik-2.-seje-OGDTK-2019.pdf'
        #         }],
        #     'session_name': '2. seja Odbora za gospodarsko dejavnost, turizem in kmetijstvo MS MOL',
        #     'agenda_name': 'Letno poročilo javnega zavoda Turizem Ljubljana za poslovno leto 2018',
        #     'date': datetime.datetime(2019, 4, 10, 0, 0),
        #     'time': '17:00',
        #     'classification': 'Odbori mestnega sveta',
        #     'body_name': 'Odbor za gospodarske dejavnosti, turizem in kmetijstvo',
        #     'order': 1,
        #     'links': []
        # }

        working_body_id, added_org = data_storage.get_or_add_organization(
            data['body_name'],
            {
                'name': data['body_name'].strip(),
                'parser_names': data['body_name'].strip(),
                'classification': 'committee'
            }
        )

        start_time = data['date']
        start_time = start_time + timedelta(
            hours=int(data['time'].split(':')[0]),
            minutes=int(data['time'].split(':')[1]))

        session_id, added = self.data_storage.add_or_get_session({
            'name': data['session_name'].strip(),
            'organization': working_body_id,
            'organizations': [working_body_id],
            'start_time': start_time.isoformat(),
            'mandate': self.data_storage.mandate_id
        })

        if added:
            for note in data['notes']:
                self.data_storage.set_link({
                'session': session_id,
                'url': f'{settings.BASE_URL}{note["url"]}',
                'name': f'{note["text"]}'
            })

        agenda_item_id, added = self.data_storage.get_or_add_agenda_item({
            'order': data['order'],
            'name': data['agenda_name'],
            'datetime': start_time.isoformat(),
            'session': session_id,
            'text': data['agenda_name'],
        })
        if added:
            for link in data['links']:
                # save links
                link_data = {
                    'agenda_item': agenda_item_id,
                    'url': link['url'],
                    'name': link['title'],
                }
                tag = link.get('tag', None)
                if tag:
                    link_data.append({'tag': [tag]})
                self.data_storage.set_link(link_data)
