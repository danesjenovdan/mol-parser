from parlaparser.data_parsers.base_parser import BaseParser
import logging


class CommitteeParser(BaseParser):
    def __init__(self, data, data_storage):
        super().__init__(data_storage)
        data = data

        organization_id, added_org = data_storage.get_or_add_organization(
            data['org_name'],
            {
                'name': data['org_name'],
                'parser_names': data['org_name'],
                'classification': data['classification']
            }
        )

        person_id, added_person = data_storage.get_or_add_person(
            data['name'],
            {
                'name': data['name'],
                'parser_names': data['name']
            }
        )
        
        data_storage.add_membership(
            {
                'member': person_id,
                'organization': organization_id,
                'on_behalf_of': None,
                'start_time': data_storage.mandate_start_time.isoformat(),
                'role': data['role'] if data['role'] else 'member',
                'mandate': data_storage.mandate_id
            }
        )

