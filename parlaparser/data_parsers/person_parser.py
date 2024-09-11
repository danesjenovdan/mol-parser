from parlaparser.data_parsers.base_parser import BaseParser
import logging


class PersonParser(BaseParser):
    def __init__(self, data, data_storage):
        super().__init__(data_storage)
        data = data

        organization = data_storage.organization_storage.get_or_add_object(
            {
                "name": data["org_name"],
                "parser_names": data["org_name"],
                "classification": "pg",
            }
        )
        if organization.is_new:
            data_storage.parladata_api.organizations_memberships.set(
                {
                    "member": organization.id,
                    "organization": data_storage.main_org_id,
                    "mandate": data_storage.mandate_id,
                }
            )

        person = data_storage.people_storage.get_or_add_object(
            {
                "name": data["name"],
                "parser_names": data["name"],
            }
        )
        if person.is_new:
            data_storage.membership_storage.get_or_add_object(
                {
                    "member": person.id,
                    "organization": organization.id,
                    "on_behalf_of": None,
                    "start_time": data_storage.mandate_start_time.isoformat(),
                    "role": data["role"] if data["role"] else "member",
                    "mandate": data_storage.mandate_id,
                }
            )
            data_storage.membership_storage.get_or_add_object(
                {
                    "member": person.id,
                    "organization": data_storage.main_org_id,
                    "on_behalf_of": organization.id,
                    "start_time": data_storage.mandate_start_time.isoformat(),
                    "role": "voter",
                    "mandate": data_storage.mandate_id,
                }
            )
