from parlaparser.data_parsers.base_parser import BaseParser
import logging


class PersonParser(BaseParser):
    def __init__(self, data, data_storage):
        super().__init__(data_storage)
        data = data

        organization_id, added_org = data_storage.get_or_add_organization(
            data['org_name'],
            {
                'name': data['org_name'],
                'parser_names': data['org_name'],
                'classification': 'pg'
            }
        )
        if added_org:
            data_storage.add_org_membership(
                {
                    'member': organization_id,
                    'organization': data_storage.main_org_id,
                    'mandate': data_storage.mandate_id
                }
            )

        person_id, added_person = data_storage.get_or_add_person(
            data['name'],
            {
                'name': data['name'],
                'parser_names': data['name']
            }
        )
        if added_person:
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
            data_storage.add_membership(
                {
                    'member': person_id,
                    'organization': data_storage.main_org_id,
                    'on_behalf_of': organization_id,
                    'start_time': data_storage.mandate_start_time.isoformat(),
                    'role': 'voter',
                    'mandate': data_storage.mandate_id
                }
            )
