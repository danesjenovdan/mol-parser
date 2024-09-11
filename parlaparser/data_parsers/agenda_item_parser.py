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


        session = self.data_storage.session_storage.get_or_add_object({
            'name': data['session_name'],
            'organizations': [self.data_storage.main_org_id],
            'start_time': start_time.isoformat(),
            'mandate': self.data_storage.mandate_id
        })
        if session.is_new and data.get("session_notes", {}):
            # add notes
            link_data = {
                'session': session.id,
                'url': data['session_notes']['url'],
                'name': data['session_notes']['title'],
            }
            self.data_storage.set_link(link_data)

        agenda_item = session.agenda_items_storage.get_or_add_object({
            'name': data['agenda_name'].strip(),
            'datetime': start_time.isoformat(),
            'session': session.id,
            'order': data['order']
        })
        if agenda_item.is_new:
            for link in data['links']:
                # save links
                link_data = {
                    'agenda_item': agenda_item.id,
                    'url': link['url'],
                    'name': link['title'],
                    'tags': [link['tag']]
                }
                self.data_storage.parladata_api.links.set(link_data)
