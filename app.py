from flask import Flask, render_template, request, Response, redirect, url_for, jsonify
from web3 import Web3
from eth_account import Account
import threading
import webbrowser
import time
import ast
import json
import importlib.util

app = Flask(__name__)


def load_networks():
    spec = importlib.util.spec_from_file_location("networks", "networks.py")
    networks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(networks)
    return networks.NETWORKS


def save_networks(networks_dict):
    with open("networks.py", "w", encoding="utf-8") as f:
        f.write("NETWORKS = ")
        json.dump(networks_dict, f, indent=4, ensure_ascii=False)


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
    return render_template("index.html", networks=load_networks())


@app.route("/tokens")
def tokens():
    network = request.args.get("network")
    net = load_networks().get(network)
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
    networks = load_networks()

    def generate():
        net = networks.get(network)
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

    return Response(generate(), mimetype='text/event-stream')


@app.route("/add-token", methods=["GET", "POST"])
def add_token():
    if request.method == "GET":
        return render_template("add_token.html", networks=load_networks().keys())

    network = request.form["network"]
    name = request.form["name"].strip().upper()
    address = request.form["address"].strip()
    decimals = 18

    networks_dict = load_networks()

    if any(t["address"].lower() == address.lower() for t in networks_dict.get(network, {}).get("tokens", [])):
        return redirect(url_for("index"))

    networks_dict.setdefault(network, {}).setdefault("tokens", []).append({
        "name": name,
        "address": address,
        "decimals": decimals
    })

    save_networks(networks_dict)
    return redirect(url_for("index"))


@app.route("/manage-tokens")
def manage_tokens():
    return render_template("manage_tokens.html", networks=load_networks())


@app.route("/edit-token", methods=["POST"])
def edit_token():
    network = request.form["network"]
    original_address = request.form["original_address"].strip().lower()
    name = request.form["name"].strip()
    address = request.form["address"].strip()
    decimals = int(request.form["decimals"])

    networks = load_networks()
    tokens = networks.get(network, {}).get("tokens", [])

    for token in tokens:
        if token["address"].lower() == original_address:
            token["name"] = name
            token["address"] = address
            token["decimals"] = decimals
            break

    save_networks(networks)
    return redirect(url_for("manage_tokens"))


@app.route("/delete-token", methods=["POST"])
def delete_token():
    network = request.form["network"]
    address = request.form["address"].strip().lower()

    networks = load_networks()
    tokens = networks.get(network, {}).get("tokens", [])
    networks[network]["tokens"] = [t for t in tokens if t["address"].lower() != address]

    save_networks(networks)
    return redirect(url_for("manage_tokens"))


@app.after_request
def add_headers(response):
    response.headers["Cache-Control"] = "no-cache"
    return response


if __name__ == "__main__":
    from waitress import serve
    port = 5000
    threading.Thread(target=lambda: time.sleep(1.5) or webbrowser.open(f"http://127.0.0.1:{port}")).start()
    serve(app, host="127.0.0.1", port=port)
