import requests
import sys

class CMLRESTClient:

    def __init__(self, base_uri, username, password, verify=False) -> None:
        self.base_uri = base_uri
        self.username = username
        self.password = password
        self.verify = verify
        self.session = requests.session()
        self.headers = { "Content-Type": "application/json"}
        self.token = None
        self.logged_in = False
    
    def cml_rest_req(
            self,
            target_uri: str,
            method: str,
            payload_data=None,
            headers={},
            request_timeout=600,
            is_login_request=False,
            op_description=""
    ) -> requests.Response :
        if not self.logged_in and not is_login_request:
            login_state = self.cml_login()
            if login_state.status_code != 200:
                self.logged_in = False
                return None
            if login_state.status_code == 200:
                self.logged_in = True
        
        request_uri = self.base_uri + target_uri
        request_headers = self.headers
        if not is_login_request:
            request_headers["Authorization"] = f"Bearer {self.token}"
        if headers != {}:
            request_headers.update(headers)
        cml_request = requests.Request(
            method=method.upper(), url=request_uri, headers=request_headers, json=payload_data
        )
        prepared_request = cml_request.prepare()
        cml_reponse = self.session.send(prepared_request, verify=self.verify, timeout=request_timeout)
        success_codes = (200,204) # PUT requests return 200 or 204. DELETE requests return 204
        if cml_reponse.status_code not in success_codes:
            print (f"Failed CML REST operation: {op_description}")
            print (f"Status code: {cml_reponse.status_code} Error: {cml_reponse.text}")
            return None
        return cml_reponse

    def cml_login(self):
        login_creds = {
            "username": self.username,
            "password": self.password
        }
        login_reponse = self.cml_rest_req(
            target_uri = "/authenticate",
            method = "POST",
            payload_data = login_creds,
            request_timeout=3.0,
            is_login_request = True
        )
        if not login_reponse:
            print (f"Login to CML {self.base_uri} failed.")
            print ("Please check the username and password and try again. Exiting...")
            sys.exit(1)
        if login_reponse.status_code == 200:
            print (f"Login to CML {self.base_uri} successful!")
            self.token = str(login_reponse.json())
        return login_reponse