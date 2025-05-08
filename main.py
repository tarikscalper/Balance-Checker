import csv
from web3 import Web3
from eth_account import Account
from networks import NETWORKS
from config import ACTIVE_NETWORK, TOKEN_NAME

# Завантаження гаманців
with open("wallets.txt", "r") as f:
    wallets = [line.strip() for line in f if line.strip()]

def is_private_key(s):
    s = s.lower().replace("0x", "")
    return len(s) == 64 and all(c in "0123456789abcdef" for c in s)

def get_address_from_input(value):
    value = value.strip()
    if is_private_key(value):
        return Account.from_key(value).address.lower()
    else:
        return Web3.to_checksum_address(value)

def get_balance(w3, address):
    try:
        value = w3.eth.get_balance(address) / 1e18
        return round(value, 6)
    except:
        return "err"

def get_token_balance(w3, address, token):
    abi = [{
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }]
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(token["address"]), abi=abi)
        balance = contract.functions.balanceOf(address).call()
        value = balance / (10 ** token["decimals"])
        return round(value, 6)
    except:
        return "err"

# Отримання інформації про мережу
net = NETWORKS.get(ACTIVE_NETWORK)
if not net:
    raise ValueError(f"❌ Невідома мережа: {ACTIVE_NETWORK}")

w3 = Web3(Web3.HTTPProvider(net["rpc"]))
try:
    w3.eth.get_block_number()
except:
    raise ConnectionError(f"⚠️ RPC для {ACTIVE_NETWORK} недоступний")

# Заголовок CSV
header = ["Wallet", "Network", "Native" if TOKEN_NAME == "" else TOKEN_NAME]
csv_data = [header]

total = 0.0  # сума всіх балансів

# Основна логіка
for wallet in wallets:
    try:
        address = get_address_from_input(wallet)
    except:
        print(f"❌ Invalid wallet: {wallet}")
        continue

    if TOKEN_NAME == "":
        value = get_balance(w3, address)
    else:
        token_list = net.get("tokens", [])
        token = next((t for t in token_list if t["name"].upper() == TOKEN_NAME.upper()), None)
        if not token:
            print(f"❌ Токен {TOKEN_NAME} не знайдено в {ACTIVE_NETWORK}")
            continue
        value = get_token_balance(w3, address, token)

    if isinstance(value, float):
        total += value
        display_value = format(value, ".6f")
    else:
        display_value = value

    csv_data.append([address, ACTIVE_NETWORK, display_value])
    print(f"✅ {address} | {ACTIVE_NETWORK} | {'Native' if TOKEN_NAME == '' else TOKEN_NAME}: {display_value}")

# Запис у CSV
with open("balances.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(csv_data)

print(f"\n📄 balances.csv збережено.")
print(f"\n🧮 Сума всіх {'нативних' if TOKEN_NAME == '' else TOKEN_NAME} токенів: {format(total, '.6f')}")
