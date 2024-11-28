from cml.lab import CMLLab
import sys

class CMLLink:
    def __init__(self) -> None:
        self.id = ""
    
    @staticmethod
    def connect_link(cml_lab: CMLLab, interface_set: tuple) -> str:
        target_uri = f"/labs/{cml_lab.id}/links"
        rest_payload = {
            "src_int": interface_set[0],
            "dst_int": interface_set[1]
        }
        r = cml_lab.client.cml_rest_req(
            target_uri = target_uri,
            method ="POST",
            payload_data = rest_payload
        )
        if not r:
            print (f"Failed to create links between interfaces {interface_set[0]} and {interface_set[1]}. Exiting...")
            sys.exit()
        return r.json()["id"]