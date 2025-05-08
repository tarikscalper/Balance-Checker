from flask import Flask, render_template, request, Response, jsonify
from web3 import Web3
from eth_account import Account
from networks import NETWORKS
import threading
import webbrowser
import time

app = Flask(__name__)

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
        return "error"

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
        return "error"

@app.route("/")
def index():
    return render_template("index.html", networks=NETWORKS)

@app.route("/tokens")
def tokens():
    network = request.args.get("network")
    net = NETWORKS.get(network)
    if not net:
        return jsonify([])
    token_names = ["Native"] + [t["name"] for t in net.get("tokens", [])]
    return jsonify(token_names)

@app.route("/wallets-count")
def wallets_count():
    try:
        with open("wallets.txt", "r") as f:
            count = sum(1 for line in f if line.strip())
        return jsonify({"count": count})
    except:
        return jsonify({"count": 0})

@app.route("/stream")
def stream_route():
    network = request.args.get("network")
    token_name = request.args.get("token", "").strip()

    def generate():
        net = NETWORKS.get(network)
        if not net:
            yield "data: ❌ Невірна мережа\n\n"
            return

        w3 = Web3(Web3.HTTPProvider(net["rpc"]))
        try:
            w3.eth.get_block_number()
        except:
            yield f"data: ⚠️ RPC для {network} недоступний\n\n"
            return

        token_data = None
        if token_name.lower() != "native":
            token_data = next((t for t in net.get("tokens", []) if t["name"].upper() == token_name.upper()), None)
            if not token_data:
                yield f"data: ❌ Токен {token_name} не знайдено в {network}\n\n"
                return

        total = 0.0
        try:
            with open("wallets.txt", "r") as f:
                for line in f:
                    wallet = line.strip()
                    if not wallet:
                        continue

                    try:
                        address = get_address_from_input(wallet)
                    except:
                        yield f"data: ❌ Невірний гаманець: {wallet}\n\n"
                        continue

                    if token_data:
                        value = get_token_balance(w3, address, token_data)
                        token_label = token_name
                    else:
                        value = get_balance(w3, address)
                        token_label = "Native"

                    if isinstance(value, float):
                        total += value
                        value_str = f"{value:.6f}"
                    else:
                        value_str = value

                    yield f"data: ✅ {address} | {network} | {token_label}: {value_str}\n\n"
                    time.sleep(0.3)

        except Exception as e:
            yield f"data: ❌ Помилка: {str(e)}\n\n"
            return

        yield f"data: ---\n🧮 Сума: {total:.6f}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.after_request
def add_headers(response):
    response.headers["Cache-Control"] = "no-cache"
    return response

if __name__ == "__main__":
    from waitress import serve
    port = 5000
    threading.Thread(target=lambda: time.sleep(1.5) or webbrowser.open(f"http://127.0.0.1:{port}")).start()
    serve(app, host="127.0.0.1", port=port)
