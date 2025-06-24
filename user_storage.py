USERS_FILE = 'users.txt'

def add_user(user_id: int):
    user_id = str(user_id)
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = set(line.strip() for line in f)
    except FileNotFoundError:
        users = set()
    if user_id not in users:
        with open(USERS_FILE, 'a', encoding='utf-8') as f:
            f.write(user_id + '\n')

def get_all_users():
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return [int(line.strip()) for line in f if line.strip()]
    except FileNotFoundError:
        return [] 