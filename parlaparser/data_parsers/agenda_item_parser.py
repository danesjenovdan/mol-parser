from parlaparser.data_parsers.base_parser import BaseParser
from parlaparser import settings
from enum import Enum
from datetime import datetime, timedelta
import logging
import re


class AgendaItemParser(BaseParser):
    def __init__(self, data, data_storage):
        super().__init__(data_storage)
        logging.debug(data['session_name'])

        start_time = data['date']
        start_time = start_time + timedelta(
            hours=int(data['time'].split(':')[0]),
            minutes=int(data['time'].split(':')[1]))

        self.start_time = start_time


        session_id, added = self.data_storage.add_or_get_session({
            'name': data['session_name'],
            'organizations': [self.data_storage.main_org_id],
            'start_time': start_time.isoformat()
        })
        if added and 'session_notes' in data.keys():
            # add notes
            link_data = {
                'session': session_id,
                'url': data['session_notes']['url'],
                'name': data['session_notes']['title'],
            }
            self.data_storage.set_link(link_data)

        self.session_id = session_id

        agenda_item_id, added = self.data_storage.get_or_add_agenda_item({
            'name': data['agenda_name'].strip(),
            'datetime': start_time.isoformat(),
            'session': session_id,
            'order': data['order']
        })
        if added:
            for link in data['links']:
                # save links
                link_data = {
                    'agenda_item': agenda_item_id,
                    'url': link['url'],
                    'name': link['title'],
                    'tags': [link['tag']]
                }
                self.data_storage.set_link(link_data)
