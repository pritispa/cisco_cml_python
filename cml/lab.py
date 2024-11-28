import sys
from cml.client import CMLRESTClient

class CMLLab:

    def __init__(self, cml_rest_client: CMLRESTClient) -> None:
        #lab parameters
        self.lab_title=""
        self.lab_description=""
        self.lab_notes=""
        self.state=""
        self.created=""
        self.modified=""
        self.owner=""
        self.owner_username=""
        self.owner_fullname=""
        self.node_count=0
        self.link_count=0
        self.id=""
        self.groups=[]
        #helper objects below
        #please initialize the client before passing it here
        self.client=cml_rest_client
        self.target_uri="/labs"
        self.existing_node_ids_list = []

    def create_lab(self, lab_title="New Lab 1", description="Lab created via automated python script", username="admin", notes="", force_clean = False) -> bool:
        lab_exists = CMLLab.check_lab_exists(lab_title, self.client)
        if lab_exists:
            print(f"Lab with name {lab_title} already exists! Will not create the lab.")
            self.set_lab_parameters(lab_exists)
            if force_clean:
                print ("Force clean lab is set to true, will wipe, stop and delete all existing nodes of this lab.")
                self.clean_existing_lab(lab_exists["id"])
            # If lab exists, store all the node ids of the lab. if clean operation is executed, this list will be empty
            self.existing_node_ids_list = CMLLab.list_lab_node_ids(lab_id=lab_exists["id"],cml_rest_client=self.client)
            return False
        print(f"Proceeding to create the Lab {lab_title}...")
        rest_payload = {
                "title": lab_title,
                "description": description,
                "notes": notes
            }
        r = self.client.cml_rest_req(
            target_uri = self.target_uri,
            method ="POST",
            payload_data = rest_payload
        )
        if not r:
            print (f"Failed to create the lab {lab_title}. Exiting...")
            sys.exit()
        self.set_lab_parameters(r.json())
        print (f"Lab {lab_title} created successfully!")
        print (f"Lab id: {self.id}")
        return True

    def set_lab_parameters(self, parameters: dict) -> None:
        self.lab_title = parameters["lab_title"]
        self.description = parameters["lab_description"]
        self.lab_notes = parameters["lab_notes"]
        self.state = parameters["state"]
        self.created = parameters["created"]
        self.modified = parameters["modified"]
        self.owner = parameters["owner"]
        self.owner_username = parameters["owner_username"]
        self.owner_fullname = parameters["owner_fullname"]
        self.node_count = parameters["node_count"]
        self.link_count = parameters["link_count"]
        self.id = parameters["id"]
        self.groups = parameters["groups"]
    
    @staticmethod
    def check_lab_exists(lab_title: str, cml_rest_client: CMLRESTClient) -> dict:
        lab_list = CMLLab.list_labs(cml_rest_client)
        if lab_list:
            for lab_id in lab_list:
                lab_id_details = CMLLab.lab_details_by_id(lab_id, cml_rest_client)
                if lab_title == lab_id_details["lab_title"]:
                    return lab_id_details
        return None
    
    def clean_existing_lab(self, lab_id: str):
        target_uri = f"/labs/{lab_id}/nodes"
        r = self.client.cml_rest_req(
            target_uri = target_uri,
            method ="GET"
        )
        if not r:
            print (f"Failed to get all nodes for deletion in lab {lab_id}. Exiting...")
            sys.exit()
        node_ids = r.json()
        # Stop nodes
        target_uri = f"/labs/{lab_id}/stop"
        r = self.client.cml_rest_req(
            target_uri = target_uri,
            method ="PUT"
        )
        if not r:
            print (f"Failed to stop all nodes for deletion in lab {lab_id}. Exiting...")
            sys.exit()
        # Wipe nodes
        target_uri = f"/labs/{lab_id}/wipe"
        r = self.client.cml_rest_req(
            target_uri = target_uri,
            method ="PUT"
        )
        if not r:
            print (f"Failed to wipe all nodes for deletion in lab {lab_id}. Exiting...")
            sys.exit()
        # Delete nodes
        for node_id in node_ids:
            target_uri = f"/labs/{lab_id}/nodes/{node_id}"
            r = self.client.cml_rest_req(
                target_uri = target_uri,
                method ="DELETE"
            )
            if not r:
                print (f"Failed to delete node {node_id} during deletion of all nodes in lab {lab_id}. Exiting...")
                sys.exit()

    @staticmethod
    def list_lab_node_ids (lab_id: str, cml_rest_client: CMLRESTClient) -> list:
        target_uri = f"/labs/{lab_id}/nodes"
        r = cml_rest_client.cml_rest_req(
            target_uri = target_uri,
            method ="GET"
        )
        if not r:
            print (f"Failed to get all node ids for the lab: {lab_id}. Exiting...")
            sys.exit()
        return r.json()

    @staticmethod
    def list_labs(cml_rest_client: CMLRESTClient) -> list:
        target_uri = "/labs"
        r = cml_rest_client.cml_rest_req(
            target_uri = target_uri,
            method ="GET"
        )
        if not r:
            print (f"Failed to fetch lab lists")
            return None
        return r.json()
    
    @staticmethod
    def lab_details_by_id(lab_id, cml_rest_client: CMLRESTClient) -> dict:
        target_uri = f"/labs/{lab_id}"
        r = cml_rest_client.cml_rest_req(
            target_uri = target_uri,
            method ="GET"
        )
        if not r:
            print (f"Failed to fetch lab title using lab id {lab_id}")
            return None
        return r.json()