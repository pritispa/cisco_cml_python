RESET   = "\033[0m"
GREEN   = "\033[92m"
ORANGE  = "\033[93m"
RED     = "\033[91m"
BLUE    = "\033[94m"

def print_create(msg):
    print(f"{GREEN}{msg}{RESET}")

def print_update(msg):
    print(f"{ORANGE}{msg}{RESET}")

def print_delete(msg):
    print(f"{RED}{msg}{RESET}")

def print_warning(msg):
    print(f"{BLUE}{msg}{RESET}")

def print_error(msg):
    print(f"{RED}{msg}{RESET}")
