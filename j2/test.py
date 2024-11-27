import jinja2

# env = jinja2.Environment()
# print ("Hi")
# dict1 = {"x": "def"}
# template = env.from_string("Hello @ {{ x }}")
# print (type(template))
# result = template.render(dict1)
# print (result)

# env = jinja2.Environment(loader=jinja2.FileSystemLoader("./"))
# template = env.get_template("test.j2")
# result = template.render(dict1)
# print (result)

# conf1 = "default config lines"
add_conf = {
    "gw" : "192.168.1.1",
    #"ip_address" : "192.168.1.10",
    "mask": "23"
}
env = jinja2.Environment(loader=jinja2.FileSystemLoader((".")))
try:
    config_template = env.get_template("test.j2")
except jinja2.exceptions.TemplateNotFound as e:
    print ("Template NOT defined")

result = config_template.render(add_conf)
result
print (result)
JINJA_DIRECTORY = "./j2"
print (JINJA_DIRECTORY+"randonabdsbgde")

print("#####################")

# class MgmtIps:
#     MgmtSubnetsToUsedIps = {}
#     @classmethod
#     def update_used_ip(cls, used_ip: str, subnet: str):
#         if subnet in cls.MgmtSubnetsToUsedIps:
#             cls.MgmtSubnetsToUsedIps[subnet].append(used_ip)
#         else:
#             cls.MgmtSubnetsToUsedIps[subnet] = []
#             cls.MgmtSubnetsToUsedIps[subnet].append(used_ip)
#     @classmethod
#     def check_if_ip_used(cls, candidate_ip: str, subnet: str) -> bool:
#         if subnet in cls.MgmtSubnetsToUsedIps:
#             if candidate_ip in cls.MgmtSubnetsToUsedIps[subnet]:
#                 return True
#         return False
# MgmtIps.update_used_ip("192.168.1.123", "192.168.1.0/24")
# MgmtIps.update_used_ip("192.168.1.12", "192.168.1.0/24")
# ip = "192.168.1.13"
# subnet = "192.168.1.0/24"
# print (f"ip {ip} is used: "+str(MgmtIps.check_if_ip_used(ip, subnet)))

print ("### End ###")